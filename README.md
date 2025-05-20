ClickClinic – Flask-Based Medical Appointment Platform
**The `my-feature-branch` is the main and active branch of this project.** 
A full-featured Flask web application that enables doctors, patients, and nurses to manage appointments, availability, medical records, and notifications — all wrapped in a clean Dockerized deployment.

---

 How to Run This App with Docker (No Python Needed)

> You only need [Docker Desktop](https://www.docker.com/products/docker-desktop) installed.

 1. Clone the Repository:
```bash
git clone https://github.com/danaelchami/430.git
cd 430
```

 2. Switch to the Main Feature Branch:
```bash
git checkout my-feature-branch
```

 3. Run It:
```bash
docker-compose up --build
```

Then open your browser to:  
[http://localhost:5000](http://localhost:5000)

---

Note About Branches

> The `my-feature-branch` is the main and active branch of this project.  
> It contains the latest version, all up-to-date commits, and is the version you should run and review.

---

Project Structure

```
├── app.py                  # Main Flask app
├── Dockerfile              # Container setup
├── docker-compose.yml      # Dev environment launcher
├── requirements.txt        # Python dependencies
├── models.py / forms.py    # Database & form logic
├── templates/              # Jinja2 templates
├── instance/               # Volume-mounted SQLite DB
├── static/                 # Images, styles
└── README.md               # This file
```

---

Tech Stack

- Python 3.12
- Flask 3.1 + SQLAlchemy
- Docker + Docker Compose  
- Flask-WTF Forms  
- Jinja2 Templates
