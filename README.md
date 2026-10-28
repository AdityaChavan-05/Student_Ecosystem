# Student_Ecosystem
# Student Ecosystem 🎓

**Student Ecosystem** is a web-based platform designed to help engineering students access relevant technology news and college updates in one place.

The goal is to reduce the time students spend searching across multiple websites by bringing useful information together in a simple, student-friendly interface.

## ✨ Features

### 1. Branch-Specific Engineering News

* Browse technology and engineering news based on your academic branch.
* Supported branches include Computer Science, Artificial Intelligence, Electronics, Mechanical, Civil, and Electrical Engineering.
* View article titles, sources, publication dates, and links to original articles.
* Get concise, AI-generated summaries to understand important developments quickly.
* Refresh the news feed to request updated results.

### 2. College Updates

* View college notices, examination updates, events, and academic announcements.
* Retrieve relevant information from the official college website.
* Configure the college website through an environment variable.

**Note:** College updates require the correct official college website URL to be configured. Until that URL is added and tested, this feature may not display college-specific information.

### 3. AI-Powered Summarization

* Uses Google's Gemini API to generate concise news summaries.
* Helps students understand articles without reading every full article.
* Keeps summaries focused on the main information.

### 4. Caching and Data Management

* Uses Supabase for optional server-side caching.
* Caching can reduce repeated requests and unnecessary processing.
* The application can operate without Supabase configured, although database-backed caching will be unavailable.

### 5. Responsive Web Interface

* Separate pages for the main dashboard, engineering news, and college updates.
* Simple navigation and branch selection.
* Responsive styling for different screen sizes.

## 🛠️ Technologies Used

| Technology        | Purpose                                |
| ----------------- | -------------------------------------- |
| Python            | Backend programming                    |
| Flask             | Web application and API routes         |
| HTML              | Webpage structure                      |
| CSS               | Styling and responsive layout          |
| JavaScript        | Frontend interactions and API requests |
| Google Gemini API | AI-generated news summaries            |
| Google News RSS   | Engineering news discovery             |
| Supabase          | Optional caching and data storage      |
| Requests          | HTTP requests                          |
| Feedparser        | RSS feed processing                    |
| Beautiful Soup    | HTML and text cleaning                 |
| python-dotenv     | Environment variable management        |

## 📁 Project Structure

```text
Student-Ecosystem/
├── app.py
├── config.py
├── categories.py
├── news_fetcher.py
├── college_fetcher.py
├── ai_summarizer.py
├── data_cleaner.py
├── database.py
├── requirements.txt
├── .env.example
├── .gitignore
└── frontend/
    ├── index.html
    ├── news.html
    ├── college.html
    ├── style.css
    └── script.js
```

## ⚙️ Requirements

Before running the project, install:

* Python 3.11 or newer
* Git (optional, but useful for cloning the repository)
* A Google Gemini API key for AI-generated summaries
* A Supabase project if you want database-backed caching

Python package versions and dependencies are listed in `requirements.txt`.

## 🚀 Getting Started

### Step 1: Download the project

Clone the repository:

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
```

Replace `YOUR_GITHUB_REPOSITORY_URL` with the actual URL of this repository.

Alternatively, click **Code → Download ZIP** on GitHub and extract the project folder.

### Step 2: Open the project

Open the `Student-Ecosystem` folder in Visual Studio Code.

### Step 3: Create a virtual environment

Open the VS Code terminal and run:

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can run the environment's Python executable directly instead:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Step 4: Install dependencies

With the virtual environment activated, run:

```bash
python -m pip install -r requirements.txt
```

### Step 5: Configure environment variables

Create a copy of `.env.example` named `.env` in the project's root directory.

Fill in the required values in `.env`:

```env
SECRET_KEY=replace-with-a-random-secret
FLASK_DEBUG=false

AI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.8-flash

SUPABASE_URL=
SUPABASE_KEY=

COLLEGE_WEBSITE_URL=
```

Replace the example values with your own configuration.

* `SECRET_KEY`: Use a secure, randomly generated secret.
* `AI_API_KEY`: Your Google Gemini API key.
* `GEMINI_MODEL`: The Gemini model to use for summarization.
* `SUPABASE_URL`: Your Supabase project URL; optional if you are not using Supabase.
* `SUPABASE_KEY`: Your appropriate Supabase API key; optional if you are not using Supabase.
* `COLLEGE_WEBSITE_URL`: The official college website URL. Leave blank until the correct URL is available.

**Security:** Never commit your `.env` file, API keys, database credentials, or other secrets to GitHub. Use environment variables or your hosting provider's secret-management settings in production.

### Step 6: Run the application

Start the Flask server:

```bash
python app.py
```

If you are using the virtual environment directly on Windows:

```powershell
.\.venv\Scripts\python.exe app.py
```

Once the server starts, open the local address shown in your terminal. The default address is:

```text
http://127.0.0.1:5000
```

Keep the terminal running while using the application.

## 🗄️ Optional Supabase Setup

Supabase-backed caching requires a table named `app_cache`.

Create the table in the Supabase SQL Editor using:

```sql
CREATE TABLE IF NOT EXISTS public.app_cache (
    cache_key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);
```

Configure `SUPABASE_URL` and `SUPABASE_KEY` in your environment.

**Important:** Configure database permissions and Row Level Security appropriately before using the table in production. Use a server-side secret or service-role key only on the backend, never in frontend JavaScript. Do not expose privileged database credentials publicly.

## 🔌 API Endpoints

| Endpoint               | Method | Purpose                                 |
| ---------------------- | ------ | --------------------------------------- |
| `/`                    | GET    | Main dashboard                          |
| `/news`                | GET    | Engineering news page                   |
| `/college`             | GET    | College updates page                    |
| `/api/health`          | GET    | Application health check                |
| `/api/branches`        | GET    | Available engineering branches          |
| `/api/news`            | GET    | Retrieve engineering news and summaries |
| `/api/college-updates` | GET    | Retrieve college updates                |

Example news request:

```text
/api/news?branch=Computer%20Science&limit=8
```

Example college updates request:

```text
/api/college-updates?limit=30
```

The availability and completeness of returned data depend on external news feeds, API configuration, and the accessibility of the college website.

## 🔐 Environment Variables

| Variable              | Required?                             | Purpose                              |
| --------------------- | ------------------------------------- | ------------------------------------ |
| `SECRET_KEY`          | Recommended                           | Flask secret key                     |
| `FLASK_DEBUG`         | No                                    | Enables or disables Flask debug mode |
| `AI_API_KEY`          | Required for AI summaries             | Google Gemini API key                |
| `GEMINI_MODEL`        | No                                    | Gemini model identifier              |
| `SUPABASE_URL`        | No                                    | Supabase project URL                 |
| `SUPABASE_KEY`        | No                                    | Backend Supabase API key             |
| `COLLEGE_WEBSITE_URL` | Required for college-specific updates | Official college website URL         |

## 📌 Current Project Status

Student Ecosystem is under development.

The initial version focuses on branch-specific engineering news, AI-powered summaries, college update discovery, and a responsive frontend.

The college update feature still needs to be configured and tested with the correct official college website.

Further development may include academic resources, improved filtering, additional data sources, and deployment.

## 🔮 Future Improvements

* Add academic notes, study materials, and learning resources.
* Improve college website crawling and announcement detection.
* Add search, filters, and bookmarking.
* Improve caching and error handling.
* Add student accounts and personalized preferences.
* Deploy the application for public access.
* Improve accessibility and mobile usability.

## 🎯 Project Objective

The objective of Student Ecosystem is to create a centralized digital companion for engineering students, helping them stay informed about their technical field and college activities through a convenient, AI-assisted platform.

---

**Built as an engineering student project.**
