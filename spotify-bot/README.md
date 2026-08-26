# 🎧 اسپاتی‌دانلودر — ربات تلگرامی دانلود رایگان از اسپاتیفای

ربات تلگرامی که **آهنگ، آلبوم و پلی‌لیست** اسپاتیفای رو پیدا می‌کنه و **رایگان** به‌صورت MP3/M4A برات می‌فرسته.
هم در **چت خصوصی** و هم در **گروه‌ها** کار می‌کنه.

## ✨ ویژگی‌ها

- 🎵 دانلود **تک‌آهنگ** — بدون نیاز به هیچ کلیدی!
- 💿 دانلود **آلبوم** و 📃 **پلی‌لیست** (با کلید رایگان Spotify API)
- 🎚 انتخاب کیفیت: MP3 128 / 192 / 320 و M4A 192
- 🔍 **جستجوی هوشمند** در یوتیوب — امتیازدهی به نتایج بر اساس عنوان، آرتیست، مدت دقیق و ویو
- 📊 **نوار پیشرفت** دانلود زنده + گزارش تک‌تک آهنگ‌ها در آلبوم/پلی‌لیست
- 👥 پشتیبانی کامل از **گروه** (با منشن `@bot` یا ری‌پلای)
- ⏱ ضد اسپم (rate-limit) + **آمار ماندگار** و تنظیمات کیفیت شخصی هر کاربر
- 🐳 آماده‌ی **Docker** + نمونه‌ی **systemd**
- 🧱 کد تمیز و ماژولار (aiogram 3، asyncio، aiohttp، yt-dlp)

## 🧠 چطور کار می‌کنه؟

1. لینک اسپاتیفای میاد → **متادیتا** (عنوان، آرتیست، مدت) از Spotify Web API یا oEmbed خوانده می‌شه
2. **جستجو در یوتیوب** با yt-dlp + امتیازدهی هوشمند برای پیدا کردن بهترین ورژن
3. دانلود بهترین کیفیت صوتی و **تبدیل به MP3/M4A** با ffmpeg
4. **ارسال فایل** به چت (با رعایت سقف ۵۰ مگابایت تلگرام)

## 📁 ساختار پروژه

```
spotify-bot/
├── bot.py               # نقطهٔ ورود: Bot + Dispatcher + polling
├── config.py            # تنظیمات از .env (همه‌چیز قابل پیکربندی)
├── models.py            # ساختارهای داده: Track / Collection
├── spotify.py           # سرویس اسپاتیفای: API رسمی + oEmbed + اسکرپ fallback
├── downloader.py        # جستجوی هوشمند یوتیوب + دانلود با yt-dlp + نوار پیشرفت
├── jobs.py              # مدیریت سفارش‌ها (دکمه‌های شیشه‌ای + TTL)
├── store.py             # آمار و تنظیمات کاربر (JSON + قفل + نوشتن اتمیک)
├── context.py           # کانتکست مشترک هندلرها
├── keyboards.py         # سازنده‌های کیبورد inline
├── utils.py             # پارس لینک، اعداد فارسی، rate-limit و ...
├── handlers/
│   ├── commands.py      # /start /help /quality /stats /ping
│   ├── links.py         # ورودی لینک‌های اسپاتیفای (گروه + خصوصی)
│   ├── callbacks.py     # انتخاب کیفیت + اجرای دانلود
│   └── errors.py        # catch-all خطاها
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── railway.json           # پیکربندی Railway (بیلدر Dockerfile + restart ALWAYS)
└── README.md
```

## 🚀 نصب

### پیش‌نیازها

- Python **3.10+**
- `ffmpeg` (لینوکس: `sudo apt install ffmpeg` | مک: `brew install ffmpeg`)

### مراحل

```bash
# 1) کد رو دانلود کن و وارد شو
git clone <آدرس-ریپازیتوری> && cd spotify-bot

# 2) تنظیمات
cp .env.example .env
nano .env   # BOT_TOKEN رو وارد کن

# 3) نصب وابستگی‌ها
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 4) اجرا!
python bot.py
```

### 🎵 کلید Spotify API (رایگان — برای آلبوم/پلی‌لیست)

1. برو به [developer.spotify.com](https://developer.spotify.com/dashboard) و با اکانت اسپاتیفیا لاگین کن
2. **Create Item** → یه اپ بساز (Redirect URI لازم نیست)
3. `Client ID` و `Client Secret` رو در `.env` بگذار:

```env
SPOTIFY_CLIENT_ID=xxxxxxxxxxxxxxxx
SPOTIFY_CLIENT_SECRET=xxxxxxxxxxxxxxxx
```

> ⚠️ بدون کلید، دانلود **تک‌آهنگ** کاملاً کار می‌کنه؛ فقط لیست آلبوم/پلی‌لیست خوانده نمی‌شه.

## 🐳 Docker

```bash
cp .env.example .env   # توکن رو بزن
docker compose up -d --build
docker compose logs -f
```

## 🚂 دیپلوی روی Railway (ساده‌ترین راه)

ربات **long polling** استفاده می‌کنه، پس نیازی به public network/پورت باز نیست — روی Railway عالی می‌نشیند.

### مراحل

1. **ریپازیتوری رو push کن** (GitHub/GitLab). `.env` توی `.gitignore` هست و upload نمی‌شه — حتماً همین‌طور باشه.
2. وارد [railway.app](https://railway.app) شو → **New Project → Deploy from GitHub repo** → ریپازیتوری رو انتخاب کن.
3. توی داشبورد: **Service → Variables** و متغیرها رو بزن:
   - `BOT_TOKEN` (الزامی)
   - `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` (اختیاری، برای آلبوم/پلی‌لیست)
   - بقیه (کیفیت، rate-limit و …) اختیاری‌ان — پیش‌فرض‌ها مناسب‌اند.
4. **Build خودکار** انجام می‌شه: `railway.json` بیلدر رو روی `DOCKERFILE` قفل کرده، پس همون `Dockerfile` پروژه اجرا می‌شه و `ffmpeg` هم خودکار نصب می‌شه. (اگر بیلدر روی Railpack/Nixpacks موند، دستی از Settings روی **Dockerfile** بگذار.)
5. توی تب **Deployments** لاگ‌ها رو ببین — وقتی `🚀 polling شروع شد` دیدی، بات زنده‌ست!

### 💾 ماندگاری داده (Volume)

فایل‌سیستم Railway با هر دیپلی ریست می‌شه. برای اینکه **آمار و تنظیمات کاربر** پاک نشوند:

1. داشبورد → **Service → Volumes → Add Volume** → مسیر: `/data`
   (یا با CLI: `railway add-volume --path /data`)
2. توی **Variables** این دو را اضافه کن:
   ```
   DATA_DIR=/data
   DOWNLOAD_DIR=/data/downloads
   ```
3. دوباره deploy کن. از این به بعد `stats.json` و `settings.json` روی volume ذخیره می‌شوند.

> بدون Volume هم همه‌چیز کار می‌کنه — فقط آمار و کیفیت شخصی بعد از هر دیپلی صفر می‌شود.

### ⚙️ نکات Railway

- **Restart policy** روی `ALWAYS` تنظیم شده (`railway.json`) — اگر ربات کرش کند، خودکار برمی‌گردد.
- پولینگ یعنی **سقف درخواست شبکه‌ای خاصی نداریم**، ولی مصرف CPU/حافظه در هر لحظه محاسبه می‌شود؛ دانلودهای سنگین هم‌زمان پشت `Semaphore(3)` صف می‌شوند و فشار زیاد نمی‌شود.
- اگه بیلد خراب بود، مطمئن شو `ffmpeg` توی Dockerfile هنوز هست (Railway آن را با apt نصب می‌کند).

## 🖥 systemd (اجرای دائمی روی سرور)

`/etc/systemd/system/spotify-bot.service`:

```ini
[Unit]
Description=Spotify Downloader Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/opt/spotify-bot
EnvironmentFile=/opt/spotify-bot/.env
ExecStart=/opt/spotify-bot/.venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now spotify-bot
journalctl -u spotify-bot -f
```

## ⚙️ تنظیمات (`.env`)

| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `BOT_TOKEN` | — | توکن از @BotFather (الزامی) |
| `SPOTIFY_CLIENT_ID` / `SECRET` | خالی | کلیدهای رایگان Spotify Web API |
| `DEFAULT_QUALITY` | `192` | 128 / 192 / 320 |
| `DEFAULT_FORMAT` | `mp3` | mp3 / m4a |
| `MAX_TRACKS_PER_JOB` | `20` | سقف آهنگ در هر آلبوم/پلی‌لیست |
| `RATE_LIMIT_SECONDS` | `15` | فاصلهٔ بین دو دانلود در هر چت (0 = آزاد) |
| `JOB_TTL_SECONDS` | `900` | اعتبار دکمه‌های انتخاب کیفیت |
| `DOWNLOAD_DIR` | `downloads` | پوشهٔ فایل‌های موقت (روی Railway: `/data/downloads`) |
| `DATA_DIR` | `data` | پوشهٔ آمار و تنظیمات (روی Railway: `/data`) |
| `LOG_LEVEL` | `INFO` | سطح لاگ |

## 📜 دستورات ربات

| دستور | توضیح |
|---|---|
| `/start` / `/help` | راهنما |
| لینک اسپاتیفای | دانلود (تک‌آهنگ / آلبوم / پلی‌لیست) |
| `/quality` | تنظیم کیفیت پیش‌فرض شخصی |
| `/stats` | آمار کلی ربات |
| `/ping` | تست سلامت |

## 🛠 خطایاب

| مشکل | راه‌حل |
|---|---|
| `BOT_TOKEN پیدا نشد` | `.env` را از `.env.example` کپی کن و توکن بزن |
| `ffmpeg پیدا نشد` | `sudo apt install ffmpeg` |
| `کلیدهای اسپاتیفای اشتباه است (401)` | Client ID/Secret را در پنل developer.spotify.com دوباره چک کن |
| لیست آلبوم خوانده نمی‌شه | کلید Spotify API را در `.env` بگذار |
| «نتیجه‌ای پیدا نشد» | آهنگ کم‌بینه/تازه‌ست؛ با اسم انگلیسی دوباره بفرست |
| `yt-dlp` خطای یوتیوب می‌ده | `pip install -U yt-dlp` (یوتیوب مدام تغییر می‌کنه) |
| فایل ارسال نمی‌شه | بزرگ‌تر از ۵۰MB است؛ کیفیت پایین‌تر انتخاب کن |

## ⚖️ قانونی

این ربات فقط برای **استفادهٔ شخصی** طراحی شده است. لطفاً از آن برای دانلود و توزیع آثار دارای حق‌تألیف بدون اجازه استفاده نکنید.
