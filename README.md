# 🏥 Hospital Hazard Assessment System

An interactive geospatial hospital risk monitoring system built with **Django**, **Folium**, **PostgreSQL**, and real-time hazard data integration.

This application visualizes hospitals on an interactive map, evaluates their operational risk, and provides AI-based hazard assessment insights.

---

## 🚀 Features

- 🌍 Interactive Map Visualization using Folium (Leaflet.js)
- 🏥 Hospital Location Mapping with Marker Clustering
- 📊 AI-Based Risk Level Prediction
- ⚠️ Hazard Zone Detection (Geospatial Polygon Analysis)
- 📍 Nearest Hospital Finder
- 🟢🟡🔴 Risk Categorization (Safe / Moderate / High Risk)
- 🏨 Detailed Hospital Information Popup:
  - Beds
  - Predicted Load
  - AI Risk Level
  - Facilities Available
- 🗺 Dynamic Hazard Boundary Highlighting
- 🧠 Backend Risk Evaluation Logic in Django
- 🐘 PostgreSQL Integration using psycopg2

---

## 🛠 Tech Stack

### Backend
- Django
- PostgreSQL
- psycopg2
- Requests
- Pillow

### Frontend
- Folium (Leaflet.js)
- HTML
- CSS
- Bootstrap (optional)

---

## 📦 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/hospital-hazard-assessment.git
cd hospital-hazard-assessment
cd hazard_app
```

### 2. Create Virtual Environment

```bash
python -m venv venv
```

Activate virtual environment:

**Windows**
```bash
venv\Scripts\activate
```

**Mac/Linux**
```bash
source venv/bin/activate
```

---

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

Or install manually:

```bash
pip install django folium psycopg2 requests pillow
```

---

### 4. Configure PostgreSQL

Create database:

```sql
CREATE DATABASE hospital_db;
```

Update `settings.py`:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'hospital_db',
        'USER': 'your_username',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

---

### 5. Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

---

### 6. Run the Development Server

```bash
python manage.py runserver
```

Open in browser:

```
http://127.0.0.1:8000/
```

---

## 🗺 System Architecture

```
User Request
      ↓
Django View
      ↓
PostgreSQL (Hospital Data)
      ↓
Hazard Evaluation Logic
      ↓
Folium Map Rendering
      ↓
Interactive Map Display
```

---

## 🧠 Risk Evaluation Logic

The system evaluates hospitals based on:

- Distance from hazard zones
- Hazard severity level
- Predicted hospital load
- Available infrastructure
- AI-based classification model

### Risk Levels

| Risk Level | Status      |
|------------|------------|
| LOW        | 🟢 Safe     |
| MEDIUM     | 🟡 Moderate |
| HIGH       | 🔴 Critical |


