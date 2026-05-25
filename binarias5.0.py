# robotesse_binarias_otimizado.py - ROBÔ OTIMIZADO COM SALVAMENTO AUTOMÁTICO
import requests
import time
import threading
from datetime import datetime
from binance.client import Client
import numpy as np
from collections import deque
import os
import json

# ============================================
# SUBSTITUIÇÃO DO WINSOUND (COMPATÍVEL COM LINUX)
# ============================================
try:
    import winsound
    SOUND_SUPORTADO = True
except ImportError:
    SOUND_SUPORTADO = False
    print("ℹ️ Modo sem beep - executando em ambiente Linux/Cloud")

# ============================================
# CONFIGURAÇÕES TELEGRAM
# ============================================
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# ============================================
# LISTA DE ATIVOS OTIMIZADA (BASEADO NO BACKTEST)
# ============================================
ATIVOS = [
    {'symbol': 'ETHUSDT', 'nome': 'ETHEREUM', 'decimais': 0},
    {'symbol': 'BTCUSDT', 'nome': 'BITCOIN', 'decimais': 0},
    {'symbol': 'BNBUSDT', 'nome': 'BNB', 'decimais': 1},
    {'symbol': 'SOLUSDT', 'nome': 'SOLANA', 'decimais': 2},
]

TIMEFRAME = '5m'
TIMEFRAME_SEGUNDOS = 300

# ============================================
# CHAVES DAS CORRETORAS (VIA VARIÁVEIS DE AMBIENTE)
# ============================================
BINANCE_API_KEY = 'TnryN2GXtAWFutlf5aIimGvPyqu95hjBJXTbwHNMiHeQr1YDFPiZ0EJJziDH6aUB'
BINANCE_SECRET_KEY = 'gZzrhHqktzYeuBwj66Sv8KxS0mnqsF8dNhlUA6LL7rdkRlAiEQzhTGx88CkRcSAv'

BYBIT_API_KEY = 'GCHEiD4GzE57AsNk64'
BYBIT_API_SECRET = 'CaG3iU9Ek0GigrAzmpysBHjRyKZ3SdwVQamb'

OKX_API_KEY = os.environ.get('OKX_API_KEY')
OKX_SECRET_KEY = os.environ.get('OKX_SECRET_KEY')

# ============================================
# ARQUIVOS DE ESTATÍSTICAS
# ============================================
ARQUIVO_ESTATISTICAS = "estatisticas_otimizado.json"
ARQUIVO_HISTORICO = "historico_trades_otimizado.json"

# ============================================
# CORES
# ============================================
class Cores:
    RESET = '\033[0m'
    VERDE = '\033[92m'
    VERDE_NEGRITO = '\033[1;92m'
    VERMELHO = '\033[91m'
    VERMELHO_NEGRITO = '\033[1;91m'
    AMARELO = '\033[93m'
    AMARELO_NEGRITO = '\033[1;93m'
    AZUL = '\033[94m'
    CIANO = '\033[96m'
    MAGENTA = '\033[95m'
    MAGENTA_NEGRITO = '\033[1;95m'
    CINZA = '\033[90m'
    BRANCO = '\033[97m'

os.system('')

# ============================================
# FUNÇÕES AUXILIARES
# ============================================
def enviar_telegram(mensagem):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': mensagem, 'parse_mode': 'HTML'}
        requests.post(url, data=payload, timeout=5)
        return True
    except:
        return False

def calcular_rsi(precos, periodo=14):
    if len(precos) < periodo + 1:
        return 50
    ganhos, perdas = [], []
    for i in range(1, len(precos)):
        diferenca = precos[i] - precos[i-1]
        if diferenca > 0:
            ganhos.append(diferenca)
            perdas.append(0)
        else:
            ganhos.append(0)
            perdas.append(abs(diferenca))
    
    media_ganho = np.mean(ganhos[:periodo])
    media_perda = np.mean(perdas[:periodo])
    
    for i in range(periodo, len(ganhos)):
        media_ganho = (media_ganho * (periodo - 1) + ganhos[i]) / periodo
        media_perda = (media_perda * (periodo - 1) + perdas[i]) / periodo
    
    if media_perda == 0:
        return 100
    rs = media_ganho / media_perda
    return 100 - (100 / (1 + rs))

def calcular_tempo_restante():
    agora = datetime.now()
    total_segundos = agora.minute * 60 + agora.second
    return TIMEFRAME_SEGUNDOS - (total_segundos % TIMEFRAME_SEGUNDOS)

# ============================================
# CLIENTES DAS CORRETORAS
# ============================================
class BybitClient:
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api.bybit.com"
        self.ultimo_oi = 0
    
    def obter_open_interest(self, symbol="BTCUSDT"):
        try:
            url = f"{self.base_url}/v5/market/open-interest"
            params = {"category": "linear", "symbol": symbol, "intervalTime": "5min"}
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('retCode') == 0 and data.get('result', {}).get('list'):
                    oi = float(data['result']['list'][0]['openInterest'])
                    variacao = 0
                    if self.ultimo_oi > 0:
                        variacao = ((oi - self.ultimo_oi) / self.ultimo_oi) * 100
                    self.ultimo_oi = oi
                    return oi, variacao
        except:
            pass
        return None, 0

class OKXClient:
    def __init__(self, api_key, secret_key):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = "https://www.okx.com/api/v5"
        self.ultimo_oi = 0
    
    def obter_open_interest(self, symbol="BTC-USDT-SWAP"):
        try:
            url = f"{self.base_url}/public/open-interest"
            params = {"instType": "SWAP", "instId": symbol}
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == '0' and data.get('data'):
                    oi = float(data['data'][0]['oi'])
                    variacao = 0
                    if self.ultimo_oi > 0:
                        variacao = ((oi - self.ultimo_oi) / self.ultimo_oi) * 100
                    self.ultimo_oi = oi
                    return oi, variacao
        except:
            pass
        return None, 0

# ============================================
# ROBÔ PRINCIPAL COM SALVAMENTO AUTOMÁTICO
# ============================================
class RoboBinariasOtimizado:
    def __init__(self):
        self.binance = None
        self.bybit = None
        self.okx = None
        
        self.dados = {}
        for ativo in ATIVOS:
            self.dados[ativo['symbol']] = {
                'nome': ativo['nome'],
                'decimais': ativo['decimais'],
                'velas': deque(maxlen=100),
                'ultimo_sinal': 0,
                'preco_atual': 0,
                'conectado': False,
                'estatisticas': {'acertos': 0, 'erros': 0, 'total_sinais': 0},
                'sinal_enviado': False,
                'sinal_pendente': None
            }
        
        self.rodando = True
        self.sinal_mostrado = False
        self.carregar_estatisticas()
        self.carregar_historico()

    def carregar_estatisticas(self):
        """Carrega estatísticas do arquivo JSON"""
        try:
            if os.path.exists(ARQUIVO_ESTATISTICAS):
                with open(ARQUIVO_ESTATISTICAS, 'r', encoding='utf-8') as f:
                    dados = json.load(f)
                    for symbol in self.dados:
                        if symbol in dados:
                            self.dados[symbol]['estatisticas'] = dados[symbol].get('estatisticas', {'acertos': 0, 'erros': 0, 'total_sinais': 0})
                            print(f"{Cores.VERDE}📊 Estatísticas carregadas para {symbol}: {self.dados[symbol]['estatisticas']['acertos']} acertos, {self.dados[symbol]['estatisticas']['erros']} erros{Cores.RESET}")
                    return
        except Exception as e:
            print(f"{Cores.AMARELO}⚠️ Erro ao carregar estatísticas: {e}{Cores.RESET}")
        
        # Se não existe, cria arquivo padrão
        self.salvar_estatisticas()

    def carregar_historico(self):
        """Carrega histórico de trades do arquivo JSON"""
        try:
            if os.path.exists(ARQUIVO_HISTORICO):
                with open(ARQUIVO_HISTORICO, 'r', encoding='utf-8') as f:
                    self.historico_trades = json.load(f)
                    print(f"{Cores.VERDE}📜 Histórico carregado: {len(self.historico_trades)} trades{Cores.RESET}")
                    return
        except:
            pass
        self.historico_trades = []

    def salvar_estatisticas(self):
        """Salva estatísticas no arquivo JSON"""
        try:
            dados = {}
            for symbol in self.dados:
                dados[symbol] = {
                    'estatisticas': self.dados[symbol]['estatisticas'],
                    'nome': self.dados[symbol]['nome'],
                    'ultima_atualizacao': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            with open(ARQUIVO_ESTATISTICAS, 'w', encoding='utf-8') as f:
                json.dump(dados, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"{Cores.VERMELHO}❌ Erro ao salvar estatísticas: {e}{Cores.RESET}")
            return False

    def salvar_historico(self):
        """Salva histórico de trades no arquivo JSON"""
        try:
            with open(ARQUIVO_HISTORICO, 'w', encoding='utf-8') as f:
                json.dump(self.historico_trades, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"{Cores.VERMELHO}❌ Erro ao salvar histórico: {e}{Cores.RESET}")
            return False

    def registrar_trade(self, symbol, nome, sinal, preco_entrada, preco_saida, variacao, acertou):
        """Registra um trade no histórico"""
        trade = {
            'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'symbol': symbol,
            'nome': nome,
            'sinal': sinal,
            'preco_entrada': preco_entrada,
            'preco_saida': preco_saida,
            'variacao': variacao,
            'resultado': 'ACERTOU' if acertou else 'ERROU'
        }
        self.historico_trades.append(trade)
        
        # Mantém apenas os últimos 1000 trades
        if len(self.historico_trades) > 1000:
            self.historico_trades = self.historico_trades[-1000:]
        
        self.salvar_historico()

    def conectar_todas(self):
        print(f"{Cores.AZUL}{'='*60}{Cores.RESET}")
        print(f"{Cores.VERDE_NEGRITO}     CONECTANDO ÀS 3 CORRETORAS...{Cores.RESET}")
        print(f"{Cores.AZUL}{'='*60}{Cores.RESET}")
        
        # Binance
        try:
            self.binance = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY)
            self.binance.ping()
            print(f"{Cores.VERDE}✅ Binance conectada{Cores.RESET}")
        except Exception as e:
            print(f"{Cores.VERMELHO}❌ Binance: {e}{Cores.RESET}")
        
        # Bybit
        try:
            self.bybit = BybitClient(BYBIT_API_KEY, BYBIT_API_SECRET)
            oi, _ = self.bybit.obter_open_interest()
            if oi:
                print(f"{Cores.VERDE}✅ Bybit conectada (OI: {oi:,.0f}){Cores.RESET}")
            else:
                print(f"{Cores.VERMELHO}❌ Bybit: sem resposta{Cores.RESET}")
        except Exception as e:
            print(f"{Cores.VERMELHO}❌ Bybit: {e}{Cores.RESET}")
        
        # OKX
        try:
            self.okx = OKXClient(OKX_API_KEY, OKX_SECRET_KEY)
            oi, _ = self.okx.obter_open_interest()
            if oi:
                print(f"{Cores.VERDE}✅ OKX conectada (OI: {oi:,.0f}){Cores.RESET}")
            else:
                print(f"{Cores.VERMELHO}❌ OKX: sem resposta{Cores.RESET}")
        except Exception as e:
            print(f"{Cores.VERMELHO}❌ OKX: {e}{Cores.RESET}")
        
        print()

    def obter_velas(self, symbol):
        if not self.binance:
            return None
        try:
            interval_map = {
                '1m': Client.KLINE_INTERVAL_1MINUTE,
                '5m': Client.KLINE_INTERVAL_5MINUTE,
                '15m': Client.KLINE_INTERVAL_15MINUTE,
                '1h': Client.KLINE_INTERVAL_1HOUR,
            }
            klines = self.binance.get_klines(symbol=symbol, interval=interval_map[TIMEFRAME], limit=100)
            
            velas = []
            for k in klines:
                velas.append({
                    'fechamento': float(k[4]),
                    'volume': float(k[5]),
                    'abertura': float(k[1]),
                    'maxima': float(k[2]),
                    'minima': float(k[3]),
                })
            return velas
        except:
            return None

    def obter_order_book(self, symbol):
        if not self.binance:
            return None
        try:
            depth = self.binance.get_order_book(symbol=symbol, limit=20)
            bid_volume = sum(float(bid[1]) for bid in depth['bids'])
            ask_volume = sum(float(ask[1]) for ask in depth['asks'])
            total = bid_volume + ask_volume
            if total > 0:
                return (bid_volume / total) * 100
            return 50
        except:
            return 50

    def prever_sinal(self, symbol, velas):
        """Preve direção usando os 4 ativos otimizados"""
        if len(velas) < 30:
            return None, 0, []
        
        vela_atual = velas[-1]
        
        precos = [v['fechamento'] for v in velas]
        volumes = [v['volume'] for v in velas[-20:]]
        
        rsi = calcular_rsi(precos, 14)
        
        media_5 = np.mean(precos[-5:])
        media_10 = np.mean(precos[-10:])
        media_20 = np.mean(precos[-20:])
        
        if media_5 > media_10 and media_10 > media_20:
            tendencia = "ALTA"
        elif media_5 < media_10 and media_10 < media_20:
            tendencia = "BAIXA"
        else:
            tendencia = "LATERAL"
        
        momentum = ((precos[-1] - precos[-6]) / precos[-6]) * 100 if len(precos) >= 6 else 0
        
        volume_medio = np.mean(volumes) if volumes else 1
        volume_relativo = vela_atual['volume'] / volume_medio if volume_medio > 0 else 1
        
        range_total = vela_atual['maxima'] - vela_atual['minima']
        corpo = abs(vela_atual['fechamento'] - vela_atual['abertura'])
        
        if vela_atual['fechamento'] > vela_atual['abertura']:
            wick_inferior = vela_atual['abertura'] - vela_atual['minima']
            wick_superior = vela_atual['maxima'] - vela_atual['fechamento']
        else:
            wick_inferior = vela_atual['fechamento'] - vela_atual['minima']
            wick_superior = vela_atual['maxima'] - vela_atual['abertura']
        
        pressao_compra = self.obter_order_book(symbol)
        
        variacao_bybit = 0
        variacao_okx = 0
        
        if self.bybit:
            symbol_oi = symbol.replace('USDT', '')
            _, var = self.bybit.obter_open_interest(symbol_oi)
            variacao_bybit = var if var else 0
        
        if self.okx:
            symbol_oi = symbol.replace('USDT', '-USDT-SWAP')
            _, var = self.okx.obter_open_interest(symbol_oi)
            variacao_okx = var if var else 0
        
        score_call = 50
        score_put = 50
        evidencias = []
        sinais_call = 0
        sinais_put = 0
        
        # 1. RSI
        if rsi < 40:
            score_call += 12
            sinais_call += 1
            evidencias.append(f"🔥 RSI {rsi:.0f} (sobrevendido) +12 CALL")
        elif rsi > 60:
            score_put += 12
            sinais_put += 1
            evidencias.append(f"🔥 RSI {rsi:.0f} (sobrecomprado) +12 PUT")
        
        # 2. Tendência
        if tendencia == "ALTA":
            score_call += 10
            sinais_call += 1
            evidencias.append(f"📈 Tendência ALTA +10 CALL")
        elif tendencia == "BAIXA":
            score_put += 10
            sinais_put += 1
            evidencias.append(f"📉 Tendência BAIXA +10 PUT")
        
        # 3. Momentum
        if momentum > 0.1:
            score_call += 10
            sinais_call += 1
            evidencias.append(f"⚡ Momentum +{momentum:.2f}% +10 CALL")
        elif momentum < -0.1:
            score_put += 10
            sinais_put += 1
            evidencias.append(f"⚡ Momentum {momentum:.2f}% +10 PUT")
        
        # 4. Reversão (wick)
        if corpo > 0:
            if wick_inferior > corpo * 1.2:
                score_call += 15
                sinais_call += 1
                evidencias.append(f"🕯️ Wick inferior grande +15 CALL")
            if wick_superior > corpo * 1.2:
                score_put += 15
                sinais_put += 1
                evidencias.append(f"🕯️ Wick superior grande +15 PUT")
        
        # 5. Order Book
        if pressao_compra > 58:
            score_call += 10
            sinais_call += 1
            evidencias.append(f"📚 OB Compra {pressao_compra:.0f}% +10 CALL")
        elif pressao_compra < 42:
            score_put += 10
            sinais_put += 1
            evidencias.append(f"📚 OB Venda {100-pressao_compra:.0f}% +10 PUT")
        
        # 6. Open Interest
        if variacao_bybit > 1:
            score_call += 5
            evidencias.append(f"🐋 Bybit OI +{variacao_bybit:.1f}%")
        elif variacao_bybit < -1:
            score_put += 5
        
        if variacao_okx > 1:
            score_call += 5
            evidencias.append(f"🐋 OKX OI +{variacao_okx:.1f}%")
        elif variacao_okx < -1:
            score_put += 5
        
        # 7. Volume
        if volume_relativo > 1.2:
            if score_call > score_put:
                score_call += 8
                evidencias.append(f"📊 Volume alto +8 CALL")
            else:
                score_put += 8
                evidencias.append(f"📊 Volume alto +8 PUT")
        
        if abs(sinais_call - sinais_put) < 2:
            return None, 0, ["⚠️ CONFLITO DETECTADO"]
        
        diferenca = abs(score_call - score_put)
        confianca = min(10, diferenca / 8)
        
        if confianca < 5:
            return None, 0, [f"⚠️ CONFIANÇA BAIXA ({confianca:.1f}/10)"]
        
        if diferenca < 12:
            return None, 0, [f"⚠️ DIFERENÇA PEQUENA ({diferenca:.0f} pts)"]
        
        if score_call > score_put:
            return "CALL", confianca, evidencias
        else:
            return "PUT", confianca, evidencias

    def atualizar_dados(self):
        for ativo in ATIVOS:
            symbol = ativo['symbol']
            velas = self.obter_velas(symbol)
            if velas and len(velas) >= 30:
                self.dados[symbol]['velas'] = deque(velas, maxlen=100)
                self.dados[symbol]['conectado'] = True
                self.dados[symbol]['preco_atual'] = velas[-1]['fechamento']

    def validar_sinal(self, symbol, sinal, preco_entrada, nome, evidencias, confianca):
        """Valida o sinal APÓS 5 minutos e SALVA o resultado"""
        
        print(f"\n{Cores.AMARELO}⏳ Validando {nome} em 5 minutos...{Cores.RESET}")
        
        # Aguarda 5 minutos e 10 segundos
        time.sleep(310)
        
        print(f"{Cores.AMARELO}🔍 Verificando resultado de {nome}...{Cores.RESET}")
        
        # Pega o preço atual
        preco_fechamento = self.dados[symbol]['preco_atual']
        
        if preco_fechamento == 0:
            print(f"{Cores.VERMELHO}❌ Não foi possível obter preço de fechamento{Cores.RESET}")
            return
        
        variacao = ((preco_fechamento - preco_entrada) / preco_entrada) * 100
        
        if sinal == 'CALL':
            acertou = preco_fechamento > preco_entrada
            resultado_real = "VERDE (subiu)" if acertou else "VERMELHA (desceu)"
        else:
            acertou = preco_fechamento < preco_entrada
            resultado_real = "VERMELHA (desceu)" if acertou else "VERDE (subiu)"
        
        decimais = 0 if 'BTC' in symbol or 'ETH' in symbol else (2 if 'SOL' in symbol else 1)
        if decimais == 0:
            entrada_str = f"${preco_entrada:,.0f}"
            fechamento_str = f"${preco_fechamento:,.0f}"
        elif decimais == 1:
            entrada_str = f"${preco_entrada:,.1f}"
            fechamento_str = f"${preco_fechamento:,.1f}"
        else:
            entrada_str = f"${preco_entrada:,.2f}"
            fechamento_str = f"${preco_fechamento:,.2f}"
        
        # ATUALIZA ESTATÍSTICAS
        if acertou:
            self.dados[symbol]['estatisticas']['acertos'] += 1
            self.dados[symbol]['estatisticas']['total_sinais'] += 1
            
            print(f"\n{Cores.VERDE_NEGRITO}{'='*65}{Cores.RESET}")
            print(f"{Cores.VERDE_NEGRITO}✅ ACERTOU! {nome}{Cores.RESET}")
            print(f"{Cores.VERDE}   Entrada: {entrada_str} → Fechamento: {fechamento_str}")
            print(f"{Cores.VERDE}   Variação: {variacao:+.2f}%")
            print(f"{Cores.VERDE}   Previsão: {sinal} ✅ {resultado_real}{Cores.RESET}")
            print(f"{Cores.VERDE_NEGRITO}{'='*65}{Cores.RESET}")
            enviar_telegram(f"✅ <b>ACERTOU</b> {nome}!\n📊 {sinal}\n💰 Entrada: {entrada_str}\n🎯 Fechamento: {fechamento_str}\n📈 Variação: {variacao:+.2f}%")
        else:
            self.dados[symbol]['estatisticas']['erros'] += 1
            self.dados[symbol]['estatisticas']['total_sinais'] += 1
            
            print(f"\n{Cores.VERMELHO_NEGRITO}{'='*65}{Cores.RESET}")
            print(f"{Cores.VERMELHO_NEGRITO}❌ ERROU! {nome}{Cores.RESET}")
            print(f"{Cores.VERMELHO}   Entrada: {entrada_str} → Fechamento: {fechamento_str}")
            print(f"{Cores.VERMELHO}   Variação: {variacao:+.2f}%")
            print(f"{Cores.VERMELHO}   Previsão: {sinal} ❌ {resultado_real}{Cores.RESET}")
            print(f"{Cores.VERMELHO_NEGRITO}{'='*65}{Cores.RESET}")
            enviar_telegram(f"❌ <b>ERROU</b> {nome}!\n📊 {sinal}\n💰 Entrada: {entrada_str}\n🎯 Fechamento: {fechamento_str}\n📉 Variação: {variacao:+.2f}%")
        
        # REGISTRA NO HISTÓRICO
        self.registrar_trade(symbol, nome, sinal, preco_entrada, preco_fechamento, variacao, acertou)
        
        # SALVA ESTATÍSTICAS (IMEDIATAMENTE)
        self.salvar_estatisticas()
        
        # Mostra taxa atualizada
        stats = self.dados[symbol]['estatisticas']
        total = stats['acertos'] + stats['erros']
        taxa = (stats['acertos'] / total * 100) if total > 0 else 0
        print(f"{Cores.CIANO}📊 Taxa {nome}: {taxa:.1f}% ({stats['acertos']}/{total}){Cores.RESET}")
        print(f"{Cores.CIANO}💾 Estatísticas salvas em {ARQUIVO_ESTATISTICAS}{Cores.RESET}")
        
        # Reseta flag
        self.dados[symbol]['sinal_enviado'] = False
        self.dados[symbol]['sinal_pendente'] = None

    def verificar_e_enviar_sinais(self):
        seg_restantes = calcular_tempo_restante()
        
        if 10 <= seg_restantes <= 15 and not self.sinal_mostrado:
            self.sinal_mostrado = True
            
            for ativo in ATIVOS:
                symbol = ativo['symbol']
                dados = self.dados.get(symbol, {})
                
                if not dados.get('conectado') or dados.get('sinal_enviado', False):
                    continue
                
                velas = list(dados['velas'])
                if len(velas) < 30:
                    continue
                
                sinal, confianca, evidencias = self.prever_sinal(symbol, velas)
                
                if sinal:
                    preco = dados['preco_atual']
                    decimais = ativo['decimais']
                    
                    if decimais == 0:
                        preco_str = f"${preco:,.0f}"
                    elif decimais == 1:
                        preco_str = f"${preco:,.1f}"
                    else:
                        preco_str = f"${preco:,.2f}"
                    
                    stats = dados.get('estatisticas', {'acertos': 0, 'erros': 0})
                    total = stats['acertos'] + stats['erros']
                    taxa = (stats['acertos'] / total * 100) if total > 0 else 0
                    
                    emoji = "🟢" if sinal == 'CALL' else "🔴"
                    acao = "COMPRAR (CALL)" if sinal == 'CALL' else "VENDER (PUT)"
                    
                    print(f"\n{Cores.MAGENTA}{'='*65}{Cores.RESET}")
                    print(f"{Cores.MAGENTA_NEGRITO}🎯 SINAL OTIMIZADO - {ativo['nome']}{Cores.RESET}")
                    print(f"{Cores.VERDE_NEGRITO if sinal == 'CALL' else Cores.VERMELHO_NEGRITO}📊 {sinal} (confiança: {confianca:.1f}/10){Cores.RESET}")
                    print(f"{Cores.CIANO}💰 Preço: {preco_str}{Cores.RESET}")
                    print(f"{Cores.CINZA}⏱️  Enviado faltando {seg_restantes}s para a vela abrir{Cores.RESET}")
                    print(f"{Cores.CINZA}📊 Taxa histórica: {taxa:.1f}%{Cores.RESET}")
                    for ev in evidencias[:4]:
                        print(f"   {ev}")
                    print(f"{Cores.MAGENTA}{'='*65}{Cores.RESET}")
                    
                    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
                        msg = f"""{emoji} <b>SINAL OTIMIZADO</b> {emoji}

📊 <b>Ativo:</b> {ativo['nome']}
📊 <b>Ação:</b> {acao}
⏱️ <b>Timeframe:</b> {TIMEFRAME}
💰 <b>Preço:</b> {preco_str}
⭐ <b>Confiança:</b> {confianca:.1f}/10
📊 <b>Taxa histórica:</b> {taxa:.1f}%

📋 <b>Indicadores:</b>
{chr(10).join(f'• {e}' for e in evidencias[:4])}

⚡ <b>Entrada:</b> Próximo candle
🎯 <b>Expiração:</b> {TIMEFRAME}

#Binarias #{symbol} #{sinal}"""
                        
                        enviar_telegram(msg)
                    
                    # Som de alerta (compatível com Linux)
                    if SOUND_SUPORTADO:
                        winsound.Beep(1000, 300)
                        winsound.Beep(1200, 300)
                    else:
                        print(f"{Cores.AMARELO}🔔 SINAL DETECTADO!{Cores.RESET}")
                    
                    self.dados[symbol]['sinal_enviado'] = True
                    self.dados[symbol]['sinal_pendente'] = {
                        'sinal': sinal,
                        'preco': preco,
                        'nome': ativo['nome'],
                        'evidencias': evidencias,
                        'confianca': confianca
                    }
                    
                    threading.Thread(
                        target=self.validar_sinal,
                        args=(symbol, sinal, preco, ativo['nome'], evidencias, confianca),
                        daemon=True
                    ).start()
                    
                    break
        
        if seg_restantes == 0 or seg_restantes > 55:
            self.sinal_mostrado = False

    def mostrar_status(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{Cores.AZUL}{'='*85}{Cores.RESET}")
        print(f"{Cores.VERDE_NEGRITO}     🎯 ROBÔ OTIMIZADO - BTC | ETH | BNB | SOL{Cores.RESET}")
        print(f"{Cores.AZUL}{'='*85}{Cores.RESET}")
        print(f"{Cores.CIANO}⏱️  Timeframe: {TIMEFRAME} | Mínimo Confiança: 5/10{Cores.RESET}")
        print(f"{Cores.CIANO}⏰ Envio: faltando 15s | Validação: após 5 minutos{Cores.RESET}")
        print(f"{Cores.CIANO}💾 Salvamento automático: {ARQUIVO_ESTATISTICAS} e {ARQUIVO_HISTORICO}{Cores.RESET}")
        print(f"{Cores.CIANO}📊 XRP e DOGE REMOVIDOS (taxa <40% no backtest){Cores.RESET}")
        print(f"{Cores.AZUL}{'-'*85}{Cores.RESET}")
        
        print(f"{Cores.BRANCO}{'Ativo':<12} {'Preço':>14} {'RSI':>6} {'Sinal':>10} {'Status':>14} {'Acertos':>10}{Cores.RESET}")
        print(f"{Cores.CINZA}{'-'*85}{Cores.RESET}")
        
        seg_restantes = calcular_tempo_restante()
        
        for ativo in ATIVOS:
            symbol = ativo['symbol']
            dados = self.dados.get(symbol, {})
            
            if dados.get('conectado') and len(dados['velas']) > 0:
                velas = list(dados['velas'])
                if len(velas) >= 20:
                    precos = [v['fechamento'] for v in velas[-20:]]
                    rsi = calcular_rsi(precos, 14)
                    preco = dados['preco_atual']
                    
                    decimais = ativo['decimais']
                    if decimais == 0:
                        preco_str = f"${preco:>12,.0f}"
                    elif decimais == 1:
                        preco_str = f"${preco:>12,.1f}"
                    else:
                        preco_str = f"${preco:>12,.2f}"
                    
                    rsi_cor = Cores.VERDE if rsi < 40 else (Cores.VERMELHO if rsi > 60 else Cores.CINZA)
                    
                    stats = dados.get('estatisticas', {'acertos': 0, 'erros': 0})
                    total = stats['acertos'] + stats['erros']
                    taxa = (stats['acertos'] / total * 100) if total > 0 else 0
                    
                    if taxa >= 60:
                        taxa_cor = Cores.VERDE
                    elif taxa >= 55:
                        taxa_cor = Cores.AMARELO
                    else:
                        taxa_cor = Cores.CINZA
                    
                    if dados.get('sinal_enviado'):
                        status = f"{Cores.VERDE}✓ ENVIADO{Cores.RESET}"
                    else:
                        status = f"{Cores.CINZA}MONITORANDO{Cores.RESET}"
                    
                    if 10 <= seg_restantes <= 15:
                        proximo = f"{Cores.AMARELO}⚡{seg_restantes}s{Cores.RESET}"
                    else:
                        proximo = f"{Cores.CINZA}{seg_restantes}s{Cores.RESET}"
                    
                    acertos_str = f"{taxa_cor}{stats['acertos']}/{stats['erros']}{Cores.RESET}" if total > 0 else f"{Cores.CINZA}0/0{Cores.RESET}"
                    
                    print(f"{ativo['nome']:<12} {preco_str}   {rsi_cor}{rsi:>3.0f}{Cores.RESET}   {proximo:<8} {status}   {acertos_str:>12}")
        
        print(f"{Cores.AZUL}{'-'*85}{Cores.RESET}")
        
        total_acertos = sum(self.dados[s]['estatisticas']['acertos'] for s in self.dados)
        total_erros = sum(self.dados[s]['estatisticas']['erros'] for s in self.dados)
        total_trades = total_acertos + total_erros
        
        if total_trades > 0:
            taxa = (total_acertos / total_trades) * 100
            if taxa >= 60:
                cor_taxa = Cores.VERDE_NEGRITO
                msg = "✅ LUCRATIVO"
            elif taxa >= 55:
                cor_taxa = Cores.AMARELO_NEGRITO
                msg = "⚠️ NO LIMITE"
            else:
                cor_taxa = Cores.VERMELHO_NEGRITO
                msg = "❌ AJUSTAR"
            
            print(f"{Cores.CIANO}📊 Taxa de acerto GLOBAL: {cor_taxa}{taxa:.1f}%{Cores.RESET} ({total_acertos}/{total_trades}) - {msg}")
        else:
            print(f"{Cores.CIANO}📊 Aguardando primeiros sinais...{Cores.RESET}")
        
        print(f"{Cores.CIANO}💾 Último salvamento: {datetime.now().strftime('%H:%M:%S')}{Cores.RESET}")
        print(f"{Cores.CINZA}🎮 Comandos: a(estat) s(salvar) r(reset) h(historico) q(sair){Cores.RESET}")
        print(f"{Cores.AZUL}{'='*85}{Cores.RESET}")

    def mostrar_estatisticas(self):
        print(f"\n{Cores.CIANO}{'='*50}{Cores.RESET}")
        print(f"{Cores.VERDE_NEGRITO}📊 ESTATÍSTICAS POR ATIVO:{Cores.RESET}")
        print(f"{Cores.CIANO}{'='*50}{Cores.RESET}")
        
        for ativo in ATIVOS:
            symbol = ativo['symbol']
            stats = self.dados[symbol]['estatisticas']
            total = stats['acertos'] + stats['erros']
            if total > 0:
                taxa = (stats['acertos'] / total * 100)
                if taxa >= 60:
                    cor = Cores.VERDE
                elif taxa >= 55:
                    cor = Cores.AMARELO
                else:
                    cor = Cores.VERMELHO
                print(f"   {ativo['nome']:<12}: {cor}{taxa:.1f}%{Cores.RESET} ({stats['acertos']}/{total})")
            else:
                print(f"   {ativo['nome']:<12}: {Cores.CINZA}Sem sinais ainda{Cores.RESET}")
        
        print(f"{Cores.CIANO}{'='*50}{Cores.RESET}")

    def mostrar_historico(self):
        print(f"\n{Cores.CIANO}{'='*60}{Cores.RESET}")
        print(f"{Cores.VERDE_NEGRITO}📜 ÚLTIMOS 10 TRADES:{Cores.RESET}")
        print(f"{Cores.CIANO}{'='*60}{Cores.RESET}")
        
        if not self.historico_trades:
            print(f"{Cores.CINZA}   Nenhum trade registrado ainda{Cores.RESET}")
            return
        
        for trade in self.historico_trades[-10:]:
            cor = Cores.VERDE if trade['resultado'] == 'ACERTOU' else Cores.VERMELHO
            print(f"   {trade['data']} | {trade['nome']:<8} | {trade['sinal']:<4} | {cor}{trade['resultado']}{Cores.RESET} | {trade['variacao']:+.2f}%")
        
        print(f"{Cores.CIANO}{'='*60}{Cores.RESET}")

    def resetar_estatisticas(self):
        for symbol in self.dados:
            self.dados[symbol]['estatisticas'] = {'acertos': 0, 'erros': 0, 'total_sinais': 0}
            self.dados[symbol]['sinal_enviado'] = False
        self.historico_trades = []
        self.salvar_estatisticas()
        self.salvar_historico()
        print(f"{Cores.AMARELO}🔄 Estatísticas e histórico resetados!{Cores.RESET}")

    def processar_comando(self, comando):
        if comando == 'a':
            self.mostrar_estatisticas()
        elif comando == 's':
            self.salvar_estatisticas()
            self.salvar_historico()
            print(f"{Cores.VERDE}💾 Estatísticas e histórico salvos!{Cores.RESET}")
        elif comando == 'r':
            self.resetar_estatisticas()
        elif comando == 'h':
            self.mostrar_historico()
        elif comando == 'q':
            self.salvar_estatisticas()
            self.salvar_historico()
            print(f"\n👋 Encerrando...")
            enviar_telegram("🛑 ROBÔ OTIMIZADO ENCERRADO")
            self.rodando = False
            return False
        return True

    def verificar_tecla(self):
        if os.name == 'nt':
            try:
                import msvcrt
                if msvcrt.kbhit():
                    return msvcrt.getch().decode('utf-8', errors='ignore').lower()
            except:
                pass
        return None

    def executar(self):
        self.conectar_todas()
        
        print(f"{Cores.CIANO}🔄 Carregando dados...{Cores.RESET}")
        self.atualizar_dados()
        
        if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            enviar_telegram(f"🤖 ROBÔ OTIMIZADO INICIADO\n📊 Ativos: BTC, ETH, BNB, SOL\n⏱️ Timeframe: {TIMEFRAME}\n⏰ Envio: faltando 15s\n💾 Salvamento automático ativado")
            print(f"{Cores.VERDE}✅ Telegram configurado!{Cores.RESET}")
        
        print(f"{Cores.VERDE_NEGRITO}🚀 Robô otimizado operacional!{Cores.RESET}")
        print(f"{Cores.CIANO}📋 Ativos monitorados:{Cores.RESET}")
        print(f"   ✅ ETHEREUM (backtest: 63.6%)")
        print(f"   ✅ BITCOIN (backtest: 54.3%)")
        print(f"   ⚠️ BNB (backtest: 50.0%)")
        print(f"   ⚠️ SOLANA (backtest: 50.0%)")
        print(f"   ❌ XRP e DOGE REMOVIDOS\n")
        print(f"{Cores.AMARELO}⏰ TIMING:{Cores.RESET}")
        print(f"   📤 Envio do sinal: faltando 15 segundos")
        print(f"   📥 Validação: após 5 minutos")
        print(f"   💾 Salvamento: automático em {ARQUIVO_ESTATISTICAS}\n")
        
        ultima_atualizacao = 0
        ultimo_status = 0
        
        while self.rodando:
            try:
                agora = time.time()
                
                if agora - ultima_atualizacao > 5:
                    self.atualizar_dados()
                    ultima_atualizacao = agora
                
                self.verificar_e_enviar_sinais()
                
                if agora - ultimo_status > 1:
                    self.mostrar_status()
                    ultimo_status = agora
                
                comando = self.verificar_tecla()
                if comando:
                    if not self.processar_comando(comando):
                        break
                
                time.sleep(0.5)
                
            except KeyboardInterrupt:
                self.salvar_estatisticas()
                self.salvar_historico()
                enviar_telegram("🛑 ROBÔ OTIMIZADO ENCERRADO")
                break
            except Exception as e:
                print(f"{Cores.VERMELHO}Erro: {e}{Cores.RESET}")
                time.sleep(5)

if __name__ == "__main__":
    robo = RoboBinariasOtimizado()
    robo.executar()
