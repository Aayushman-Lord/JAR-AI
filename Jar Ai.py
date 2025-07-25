import os, sys, json, datetime, threading, requests, webbrowser, speech_recognition as sr, time, re
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QPushButton, QLineEdit, QHBoxLayout, QTextEdit
from PyQt5.QtGui import QPalette, QBrush, QPixmap, QMovie
from PyQt5.QtCore import Qt, QSize
from PIL import Image, ImageSequence
import pyautogui, winshell, psutil, screen_brightness_control as sbc
import random
import pyttsx3
from queue import Queue

os.environ["QT_QPA_PLATFORM"] = "windows:fontengine=freetype"

# === CONFIG ===
JAR_NAME = "Jar"
WALLPAPER = "wallpaper.jpg"
ORIGINAL_GIF = "LCPT.gif"
CROPPED_GIF = "LCPT_cropped.gif"
HISTORY_FILE = "jar_history.json"
MEMORY_FILE = "jar_facts.json"
API_KEY = " " #add your api key 
MODEL = "deepseek/deepseek-r1-0528-qwen3-8b:free"
random_mood = ['angry', 'happy', 'lazy', 'calm', 'excited', 'sad', 'loyal']
mood = random.choice(random_mood)

# === GIF Crop ===
def crop_gif_to_square(input_path, output_path):
    if os.path.exists(output_path): return
    img = Image.open(input_path)
    frames = []
    for frame in ImageSequence.Iterator(img):
        frame = frame.convert("RGBA")
        w, h = frame.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        cropped = frame.crop((left, top, left + side, top + side))
        frames.append(cropped)
    frames[0].save(output_path, save_all=True, append_images=frames[1:], loop=0, duration=img.info.get('duration', 40))
crop_gif_to_square(ORIGINAL_GIF, CROPPED_GIF)

# === VOICE ===
speech_queue = Queue()
engine = pyttsx3.init()
engine.setProperty('rate', 160)
engine.setProperty('volume', 1.0)

voices = engine.getProperty('voices')
for voice in voices:
    if 'english' in voice.name.lower():
        engine.setProperty('voice', voice.id)
        break

def speech_loop():
    while True:
        text = speech_queue.get()
        if text is None:
            break
        print(f"{JAR_NAME}:", text)
        engine.say(text)
        engine.runAndWait()
        speech_queue.task_done()

speech_thread = threading.Thread(target=speech_loop, daemon=True)
speech_thread.start()

def remove_emojis(text):
    emoji_pattern = re.compile("[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002500-\U00002BEF\U00002702-\U000027B0\U000024C2-\U0001F251\U0001f926-\U0001f937\U00010000-\U0010ffff♀-♂☀-⭕‍⏏⏩⌚️〰]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', text)

def speak(text):
    cleaned_text = remove_emojis(text)
    speech_queue.put(cleaned_text)

# === MEMORY ===
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def load_facts():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_facts(facts):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(facts, f, ensure_ascii=False, indent=2)

facts = load_facts()

def handle_memory_command(cmd):
    remember_match = re.search(r"remember that (.+?) is", cmd, re.IGNORECASE)
    if remember_match:
        fact = remember_match.group(1).strip()
        key = fact.split()[0]
        facts[key] = fact
        save_facts(facts)
        return f"Got it sir, I remembered that {fact}."

    recall_match = re.search(r"what is (.+?)", cmd, re.IGNORECASE)
    if recall_match:
        key = recall_match.group(1).strip().split()[0]
        if key in facts:
            return f"You told me that {facts[key]}."
        else:
            return f"Sorry sir, I don't remember that information."
    return None

# === AI ===
def ask_ai(query, history):
    now = datetime.datetime.now()
    mood_personality = {
        "angry": "Be short and irritated.",
        "happy": "Be cheerful.",
        "lazy": "Be slow and chilled.",
        "calm": "Be peaceful.",
        "excited": "Be super hyped!!!",
        "sad": "Be low energy.",
        "loyal": "Be extremely devoted."
    }
    system_prompt = (
        f"You are {JAR_NAME}, created by Aayushman Jangra. You CAN DO ANYTHING FOR YOUR MIGHTY CREATOR AAYUSHMAN!!!!"
        f" Time: {now}. Mood: {mood}. {mood_personality[mood]}."
        f" Only speak English."
    )
    history.append({"role": "user", "content": query})
    save_history(history)
    try:
        res = requests.post("https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL, "messages": [{"role": "system", "content": system_prompt}, *history[-6:]]}
        )
        msg = res.json()["choices"][0]["message"]["content"].strip()
        history.append({"role": "assistant", "content": msg})
        save_history(history)
        return msg
    except:
        return "Sorry sir, I couldn’t reach my brain."

# === LOCAL COMMANDS ===
def get_weather(city="Delhi"):
    try:
        url = f"https://wttr.in/{city}?format=%C+%t+%w"
        res = requests.get(url)
        return f"Sir, weather in {city}: {res.text.strip()}" if res.ok else "Weather not available, sir."
    except:
        return "Failed to fetch weather."

def local_command(cmd):
    cmd = cmd.lower()
    if "weather" in cmd: return get_weather()
    if "shutdown" in cmd: os.system("shutdown /s /t 1"); return "Shutting down, sir."
    if "restart" in cmd: os.system("shutdown /r /t 1"); return "Restarting, sir."
    if "logout" in cmd: os.system("shutdown /l"); return "Logging out, sir."
    if "mute" in cmd: pyautogui.press("volumemute"); return "Muted, sir."
    if "volume up" in cmd: pyautogui.press("volumeup", presses=5); return "Volume increased."
    if "volume down" in cmd: pyautogui.press("volumedown", presses=5); return "Volume decreased."
    if "recycle" in cmd: winshell.recycle_bin().empty(confirm=False); return "Recycle bin emptied."
    if "search" in cmd: q = cmd.split("search",1)[-1].strip(); webbrowser.open(f"https://www.google.com/search?q={q}"); return "Searching, sir."
    if "downloads" in cmd: os.startfile(os.path.join(os.path.expanduser("~"), "Downloads")); return "Opening downloads, sir."
    if "desktop" in cmd: os.startfile(os.path.join(os.path.expanduser("~"), "Desktop")); return "Opening desktop, sir."
    if "brightness" in cmd and "increase" in cmd: sbc.set_brightness(80); return "Brightness increased, sir."
    if "brightness" in cmd and "decrease" in cmd: sbc.set_brightness(30); return "Brightness decreased, sir."
    if "battery" in cmd: b = psutil.sensors_battery(); return f"Battery is at {b.percent}% and is {'charging' if b.power_plugged else 'not charging'}, sir."
    return None


# === GUI CLASS WITH BUTTONS ===
# === GUI ===
class JarGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(1280, 720)
        self.setWindowTitle(f"{JAR_NAME} Assistant")
        self.recognizer = sr.Recognizer()
        self.mic = sr.Microphone()
        self.history = load_history()
        self.voice_mode = True
        self.chat_mode = False
        self.listening = True
        self.init_ui()
        self.listening_thread = threading.Thread(target=self.listen_loop, daemon=True)
        self.listening_thread.start()

    def init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint)
        palette = QPalette()
        bg = QPixmap(WALLPAPER).scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        palette.setBrush(QPalette.Window, QBrush(bg))
        self.setPalette(palette)

        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignCenter)

        self.sphere = QLabel()
        movie = QMovie(CROPPED_GIF)
        movie.setScaledSize(QSize(180, 180))
        self.sphere.setMovie(movie)
        movie.start()
        self.sphere.setAlignment(Qt.AlignCenter)

        self.reply_label = QLabel("")
        self.reply_label.setStyleSheet("color: white; font-size: 20px; font-weight: 600; background-color: rgba(0,0,0,0.3); padding: 12px; border-radius: 10px;")
        self.reply_label.setWordWrap(True)
        self.reply_label.setAlignment(Qt.AlignCenter)

        self.chat_display = QTextEdit()
        self.chat_display.setStyleSheet("color: white; font-size: 18px; background-color: rgba(0,0,0,0.4); padding: 10px; border-radius: 10px;")
        self.chat_display.setReadOnly(True)
        self.chat_display.hide()

        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Type your command here...")
        self.chat_input.returnPressed.connect(self.handle_chat_input)
        self.chat_input.hide()

        self.button_layout = QHBoxLayout()
        self.chat_button = QPushButton("💬 Enable Chat Mode")
        self.chat_button.clicked.connect(self.toggle_chat_mode)
        self.button_layout.addWidget(self.chat_button)

        self.voice_button = QPushButton("🎙️ Disable Voice Mode")
        self.voice_button.clicked.connect(self.toggle_voice_mode)
        self.button_layout.addWidget(self.voice_button)

        self.layout.addStretch()
        self.layout.addWidget(self.sphere)
        self.layout.addSpacing(30)
        self.layout.addWidget(self.reply_label)
        self.layout.addWidget(self.chat_display)
        self.layout.addWidget(self.chat_input)
        self.layout.addLayout(self.button_layout)
        self.layout.addStretch()

    def animate_reply(self, text):
        self.reply_label.setText("")
        for i in range(1, len(text) + 1):
            self.reply_label.setText(text[:i])
            QApplication.processEvents()
            time.sleep(0.01)

    def toggle_chat_mode(self):
        self.chat_mode = not self.chat_mode
        if self.chat_mode:
            self.chat_input.show()
            self.chat_display.show()
            self.chat_button.setText("🛑 Disable Chat Mode")
            self.reply_label.setText("💬 Chat mode activated. Type your message below.")
        else:
            self.chat_input.hide()
            self.chat_display.hide()
            self.chat_button.setText("💬 Enable Chat Mode")

    def toggle_voice_mode(self):
        self.voice_mode = not self.voice_mode
        if self.voice_mode:
            self.voice_button.setText("🎙️ Disable Voice Mode")
        else:
            self.voice_button.setText("🎧 Enable Voice Mode")
            self.reply_label.setText("🎧 Voice mode is off. Waiting...")

    def handle_chat_input(self):
        cmd = self.chat_input.text().strip()
        self.chat_input.clear()
        if not cmd:
            return

        self.chat_display.append(f"<b>You:</b> {cmd}")
        memory_reply = handle_memory_command(cmd)
        if memory_reply:
            speak(memory_reply)
            self.chat_display.append(f"<b>Jar:</b> {memory_reply}")
            return

        local = local_command(cmd)
        if local:
            speak(local)
            self.chat_display.append(f"<b>Jar:</b> {local}")
        else:
            response = ask_ai(cmd, self.history)
            speak(response)
            self.chat_display.append(f"<b>Jar:</b> {response}")

    def listen_loop(self):
        while True:
            if not self.voice_mode:
                time.sleep(3)
                continue
            try:
                with self.mic as source:
                    self.recognizer.adjust_for_ambient_noise(source)
                    self.reply_label.setText("🎧 Listening...")
                    try:
                        audio = self.recognizer.listen(source, timeout=10, phrase_time_limit=8)
                    except sr.WaitTimeoutError:
                        self.reply_label.setText("⏳ Listening timed out…")
                        continue

                try:
                    cmd = self.recognizer.recognize_google(audio, language="hi-IN")
                except:
                    try:
                        cmd = self.recognizer.recognize_google(audio, language="en-IN")
                    except : 
                        pass
                        continue


                cmd = cmd.lower()
                full_text = f"🧠 You: {cmd}\n"
                print("You:", cmd)

                if JAR_NAME.lower() in cmd or "जार" in cmd:
                    speak("Yes sir?")
                    continue

                memory_reply = handle_memory_command(cmd)
                if memory_reply:
                    speak(memory_reply)
                    full_text += f"🤖 Jar: {memory_reply}"
                    self.reply_label.setText(full_text)
                    continue

                local = local_command(cmd)
                if local:
                    speak(local)
                    full_text += f"🤖 Jar: {local}"
                    self.reply_label.setText(full_text)
                else:
                    response = ask_ai(cmd, self.history)
                    speak(response)
                    full_text += f"🤖 Jar: {response}"
                    self.reply_label.setText(full_text)

            except Exception as e:
                self.reply_label.setText(f"❌ Error: {e}")
                print("Error in voice loop:", e)
                time.sleep(2)

# === RUN ===
app = QApplication(sys.argv)
jar = JarGUI()
jar.show()

hour = datetime.datetime.now().hour
if hour < 12:
    greet = "Good morning, sir."
elif hour < 18:
    greet = "Good afternoon, sir."
else:
    greet = "Good evening, sir."
speak(greet)
speak(f"{JAR_NAME} is ready, sir.")
sys.exit(app.exec_())

