import logging
import re
import json
import os
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Configurazione logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Mappatura conti
CONTI = {
    'S': 'Svago',
    'R': 'Risparmi', 
    'N': 'Necessità',
    'L': 'Lavoro'
}

class GestoreConti:
    def __init__(self):
        self.saldi = {'S': 0, 'R': 0, 'N': 0, 'L': 0}
        self.movimenti_pendenti = []
        self.storico = []
        
    def aggiungi_movimento(self, importo, da_conto, a_conto, user_id):
        """Aggiunge un movimento pendente"""
        movimento = {
            'importo': float(importo),
            'da': da_conto,
            'a': a_conto,
            'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'user_id': user_id,
            'id': len(self.movimenti_pendenti)
        }
        self.movimenti_pendenti.append(movimento)
        self.storico.append(movimento.copy())
        
    def esegui_movimento(self, movimento_id):
        """Esegue effettivamente un movimento"""
        if movimento_id < len(self.movimenti_pendenti):
            movimento = self.movimenti_pendenti[movimento_id]
            self.saldi[movimento['da']] -= movimento['importo']
            self.saldi[movimento['a']] += movimento['importo']
            return True
        return False
        
    def rimuovi_movimento(self, movimento_id):
        """Rimuove un movimento pendente"""
        if movimento_id < len(self.movimenti_pendenti):
            self.movimenti_pendenti.pop(movimento_id)
            return True
        return False
        
    def get_resoconto(self):
        """Restituisce il resoconto dei movimenti pendenti"""
        if not self.movimenti_pendenti:
            return "✅ Non ci sono movimenti pendenti!"
            
        resoconto = "📋 **MOVIMENTI PENDENTI:**\n\n"
        for i, mov in enumerate(self.movimenti_pendenti):
            resoconto += f"{i+1}. Devi spostare €{mov['importo']:.2f} da {CONTI[mov['da']]} a {CONTI[mov['a']]}\n"
            resoconto += f"   📅 {mov['data']}\n\n"
            
        return resoconto
        
    def get_saldi(self):
        """Restituisce i saldi attuali"""
        saldi_text = "💰 **SALDI ATTUALI:**\n\n"
        for codice, nome in CONTI.items():
            saldi_text += f"• {nome}: €{self.saldi[codice]:.2f}\n"
        return saldi_text
        
    def salva_dati(self, filename='dati_bot.json'):
        """Salva i dati su file"""
        try:
            dati = {
                'saldi': self.saldi,
                'movimenti_pendenti': self.movimenti_pendenti,
                'storico': self.storico
            }
            with open(filename, 'w') as f:
                json.dump(dati, f, indent=2)
        except Exception as e:
            logger.error(f"Errore nel salvare i dati: {e}")
            
    def carica_dati(self, filename='dati_bot.json'):
        """Carica i dati da file"""
        try:
            with open(filename, 'r') as f:
                dati = json.load(f)
                self.saldi = dati.get('saldi', {'S': 0, 'R': 0, 'N': 0, 'L': 0})
                self.movimenti_pendenti = dati.get('movimenti_pendenti', [])
                self.storico = dati.get('storico', [])
                logger.info("Dati caricati con successo")
        except FileNotFoundError:
            logger.info("File dati non trovato, inizializzo con valori di default")
        except Exception as e:
            logger.error(f"Errore nel caricare i dati: {e}")

# Istanza globale del gestore
gestore = GestoreConti()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Messaggio di benvenuto"""
    welcome_text = """
🤖 **Benvenuto nel Bot Gestione Conti!**

📝 **Come usare il bot:**

**Per aggiungere un movimento:**
• Scrivi: `[importo] da [conto_origine] a [conto_destinazione]`
• Esempio: `50 da S a R` (sposta 50€ da Svago a Risparmi)

**I tuoi conti:**
• S = Svago
• R = Risparmi  
• N = Necessità
• L = Lavoro

**Comandi disponibili:**
• `/resoconto` - Vedi tutti i movimenti pendenti
• `/saldi` - Vedi i saldi attuali di tutti i conti
• `/esegui [numero]` - Esegui un movimento pendente
• `/cancella [numero]` - Cancella un movimento pendente
• `/imposta_saldo [conto] [importo]` - Imposta il saldo di un conto
• `/help` - Mostra questo messaggio

Inizia subito a tracciare i tuoi movimenti! 💰
    """
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mostra l'aiuto"""
    await start(update, context)

async def resoconto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mostra il resoconto dei movimenti pendenti"""
    testo = gestore.get_resoconto()
    await update.message.reply_text(testo, parse_mode='Markdown')
    gestore.salva_dati()

async def saldi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mostra i saldi attuali"""
    testo = gestore.get_saldi()
    await update.message.reply_text(testo, parse_mode='Markdown')

async def imposta_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Imposta il saldo di un conto"""
    try:
        if len(context.args) != 2:
            await update.message.reply_text("❌ Formato: /imposta_saldo [conto] [importo]\nEsempio: /imposta_saldo S 100")
            return
            
        conto = context.args[0].upper()
        importo = float(context.args[1])
        
        if conto not in CONTI:
            await update.message.reply_text(f"❌ Conto non valido. Usa: {', '.join(CONTI.keys())}")
            return
            
        gestore.saldi[conto] = importo
        await update.message.reply_text(f"✅ Saldo {CONTI[conto]} impostato a €{importo:.2f}")
        gestore.salva_dati()
        
    except ValueError:
        await update.message.reply_text("❌ Importo non valido. Usa un numero.")
    except Exception as e:
        await update.message.reply_text(f"❌ Errore: {str(e)}")

async def esegui_movimento(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Esegue un movimento pendente"""
    try:
        if len(context.args) != 1:
            await update.message.reply_text("❌ Formato: /esegui [numero]\nEsempio: /esegui 1")
            return
            
        movimento_id = int(context.args[0]) - 1
        
        if movimento_id < 0 or movimento_id >= len(gestore.movimenti_pendenti):
            await update.message.reply_text("❌ Numero movimento non valido")
            return
            
        movimento = gestore.movimenti_pendenti[movimento_id]
        
        if gestore.esegui_movimento(movimento_id):
            gestore.rimuovi_movimento(movimento_id)
            await update.message.reply_text(
                f"✅ Movimento eseguito: €{movimento['importo']:.2f} da {CONTI[movimento['da']]} a {CONTI[movimento['a']]}"
            )
            gestore.salva_dati()
        else:
            await update.message.reply_text("❌ Errore nell'esecuzione del movimento")
            
    except ValueError:
        await update.message.reply_text("❌ Numero non valido")
    except Exception as e:
        await update.message.reply_text(f"❌ Errore: {str(e)}")

async def cancella_movimento(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancella un movimento pendente"""
    try:
        if len(context.args) != 1:
            await update.message.reply_text("❌ Formato: /cancella [numero]\nEsempio: /cancella 1")
            return
            
        movimento_id = int(context.args[0]) - 1
        
        if movimento_id < 0 or movimento_id >= len(gestore.movimenti_pendenti):
            await update.message.reply_text("❌ Numero movimento non valido")
            return
            
        movimento = gestore.movimenti_pendenti[movimento_id]
        
        if gestore.rimuovi_movimento(movimento_id):
            await update.message.reply_text(
                f"🗑️ Movimento cancellato: €{movimento['importo']:.2f} da {CONTI[movimento['da']]} a {CONTI[movimento['a']]}"
            )
            gestore.salva_dati()
        else:
            await update.message.reply_text("❌ Errore nella cancellazione del movimento")
            
    except ValueError:
        await update.message.reply_text("❌ Numero non valido")
    except Exception as e:
        await update.message.reply_text(f"❌ Errore: {str(e)}")

async def gestisci_messaggio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gestisce i messaggi per aggiungere movimenti"""
    text = update.message.text.strip()
    user_id = update.effective_user.id
    
    # Pattern per riconoscere: "50 da S a R" o varianti
    pattern = r'(\d+(?:\.\d+)?)\s+da\s+([SRNL])\s+a\s+([SRNL])'
    match = re.search(pattern, text.upper())
    
    if match:
        importo = match.group(1)
        da_conto = match.group(2)
        a_conto = match.group(3)
        
        # Verifica che i conti siano diversi
        if da_conto == a_conto:
            await update.message.reply_text("❌ Non puoi spostare denaro sullo stesso conto!")
            return
            
        # Verifica che i conti esistano
        if da_conto not in CONTI or a_conto not in CONTI:
            await update.message.reply_text(f"❌ Conti non validi. Usa: {', '.join(CONTI.keys())}")
            return
            
        try:
            # Aggiunge il movimento
            gestore.aggiungi_movimento(importo, da_conto, a_conto, user_id)
            
            await update.message.reply_text(
                f"✅ Movimento aggiunto: €{float(importo):.2f} da {CONTI[da_conto]} a {CONTI[a_conto]}\n\n"
                f"Usa /resoconto per vedere tutti i movimenti pendenti"
            )
            gestore.salva_dati()
            
        except ValueError:
            await update.message.reply_text("❌ Importo non valido")
        except Exception as e:
            await update.message.reply_text(f"❌ Errore: {str(e)}")
    else:
        # Messaggio di aiuto se il formato non è riconosciuto
        await update.message.reply_text(
            "❓ Non ho capito il formato.\n\n"
            "📝 **Formato corretto:**\n"
            "`[importo] da [conto_origine] a [conto_destinazione]`\n\n"
            "**Esempio:** `50 da S a R`\n\n"
            "**Conti disponibili:** S, R, N, L\n"
            "Usa /help per vedere tutti i comandi", 
            parse_mode='Markdown'
        )

def main() -> None:
    """Avvia il bot"""
    # Legge il token dalle variabili d'ambiente (Railway)
    TOKEN = os.getenv('BOT_TOKEN')
    
    if not TOKEN:
        logger.error("❌ Token del bot non trovato! Imposta la variabile BOT_TOKEN su Railway.")
        return
    
    # Carica i dati salvati
    gestore.carica_dati()
    
    # Crea l'applicazione
    application = Application.builder().token(TOKEN).build()
    
    # Aggiungi i gestori dei comandi
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("resoconto", resoconto))
    application.add_handler(CommandHandler("saldi", saldi))
    application.add_handler(CommandHandler("imposta_saldo", imposta_saldo))
    application.add_handler(CommandHandler("esegui", esegui_movimento))
    application.add_handler(CommandHandler("cancella", cancella_movimento))
    
    # Gestore per i messaggi di testo (movimenti)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, gestisci_messaggio))
    
    # Avvia il bot
    logger.info("🤖 Bot avviato su Railway!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()