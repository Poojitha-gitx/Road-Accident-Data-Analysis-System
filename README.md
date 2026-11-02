# Road Accident Data Analysis System
### College Mini Project | Computer Science & Engineering / Information Technology

An end-to-end, full-stack analytical web platform built to record, monitor, analyze, and visualize road traffic accident data across metropolitan transit corridors and arterial road networks.

---

## 🌟 Key Highlights

- **Backend Architecture:** Python Flask RESTful backend with modular data, authentication, and query layers.
- **Authentication & RBAC:** Secure session authentication with Werkzeug password hashing, professional banking-style authentication interfaces, token & OTP password recovery, 5-minute code expiration, attempt throttling, CSRF protection, and two-tier role-based access control (**Admin** vs **User**).
- **Design System Alignment:** New authentication pages (Login, Signup, Forgot Password, Reset Password) inspired by the clean, professional visual architecture of the *Banking Transaction Analysis System* reference design (neutral ivory canvas, deep navy primary accents, accessible field controls, password visibility toggles, live strength indicators, and responsive cards).
- **Database Engine:** MySQL relational database (with seamless SQLite fallback) utilizing **parameterized SQL queries (`%s`)** to completely prevent SQL Injection vulnerabilities, backed by environment variable credentials (`.env`) and automatic schema initialization.
- **Advanced Data Processing:** **Pandas** for multi-dimensional data grouping, cross-tabulations, and time-series feature engineering; **NumPy** for descriptive statistical modeling (mean, median, standard deviation, interquartile range).
- **Analytical Chart Generation:** Dynamic **Matplotlib** visualizations rendered on-the-fly and streamed directly as high-resolution PNG charts.
- **Frontend Design:** Vanilla CSS with custom properties, dark slate glassmorphism, responsive sidebar navigation, interactive modals, and modern typography (**Outfit** & **Plus Jakarta Sans**).
- **Academic Governance & Ethics:** Clearly identified **Synthetic Demonstration Dataset**, location granularity at regional corridor scale, zero personally identifying information (PII), and formal disclaimer stating analysis demonstrates observational associations, not direct causation.

---

## 🛠️ Technology Stack

| Domain | Technology | Purpose |
| :--- | :--- | :--- |
| **Frontend** | HTML5, CSS3, JavaScript (Vanilla ES6) | Modern dashboard, glassmorphic UI, responsive sidebar, modals, multi-field search and filters |
| **Backend** | Python 3 (Flask) | Application server, routing, file streaming, CRUD validation |
| **Database** | MySQL (via `mysql-connector-python`) | Relational persistence of locations and accident records |
| **Data Analysis** | Pandas & NumPy | Grouping, aggregation, cross-tabulation, and parametric/non-parametric statistics |
| **Visualization** | Matplotlib (Agg backend) | High-resolution analytical charts (trends, donut, grouped bar, diurnal curves) |
| **Security** | `python-dotenv`, Parameterized Queries | Secure credential management, SQL injection immunity |

---

## 📊 Dataset Composition & Provenance

The system currently manages **36 verified accident records** in the TiDB Cloud production database:

1. **Approved Synthetic Demonstration Dataset (30 Records):**
   - **Provenance:** Artificially synthesized demonstration data spanning 2021 through 2026 across major Andhra Pradesh regional sectors (*Tirupati*, *Madanapalle*, *Chittoor*, *Pileru*, *Srikalahasti*, *Puttur*, *Palamaner*).
   - **Purpose:** Created specifically for reproducible academic analysis, testing, and statistical visualization with balanced distribution across years, vehicle types, weather conditions, and injury severity.
2. **Testing & Verification Records (6 Records):**
   - **Records:** `#221`, `#222`, `#224`, `#225`, `#226`, `#227`
   - **Provenance:** Created during system verification and integration testing of the interactive **"Add Accident Record"** form and live TiDB Cloud `COMMIT` pipeline (location: *Tirupati / main road*).
3. **Data Privacy & Governance:**
   - **Zero Personally Identifying Information (PII):** No names, vehicle registration plates, or personal IDs are stored.
   - **Observational Correlation:** All findings demonstrate empirical associations, not direct causation.
   - **Synthetic Dataset Notice:** All road names represent simulated sector corridors for academic simulation.

---

## 🗄️ Database Architecture & Schema

The system implements normalized relational tables as defined in `schema.sql`:

### 1. `locations` Table
Stores unique geographical corridors and arterial road names:
```sql
CREATE TABLE IF NOT EXISTS locations (
    location_id INT AUTO_INCREMENT PRIMARY KEY,
    region VARCHAR(100) NOT NULL,
    road_name VARCHAR(150) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_region (region),
    UNIQUE KEY uq_location (region, road_name)
);
```

### 2. `accidents` Table
Stores recorded accident events linked via foreign key to `locations`:
```sql
CREATE TABLE IF NOT EXISTS accidents (
    accident_id INT AUTO_INCREMENT PRIMARY KEY,
    accident_datetime DATETIME NOT NULL,
    location_id INT NOT NULL,
    vehicle_type ENUM('Bike', 'Car', 'Bus', 'Truck', 'Auto', 'Other') NOT NULL,
    severity ENUM('Minor', 'Serious', 'Fatal') NOT NULL,
    weather ENUM('Clear', 'Rainy', 'Foggy', 'Overcast', 'Windy', 'Other') DEFAULT 'Clear',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (location_id) REFERENCES locations(location_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    INDEX idx_datetime (accident_datetime),
    INDEX idx_severity (severity),
    INDEX idx_vehicle (vehicle_type)
);
```

### 3. `users` Table
Stores user accounts with role-based access control (`admin` / `user`):
```sql
CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(191) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_email (email),
    INDEX idx_user_role (role)
);
```

### 4. `otp_verifications` Table
Stores hashed 6-digit one-time passwords for signup and password reset verification:
```sql
CREATE TABLE IF NOT EXISTS otp_verifications (
    otp_id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(191) NOT NULL,
    otp_hash VARCHAR(255) NOT NULL,
    purpose VARCHAR(50) NOT NULL,
    expires_at DATETIME NOT NULL,
    attempts INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 5,
    is_used TINYINT(1) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_otp_email_purpose (email, purpose),
    INDEX idx_otp_expires (expires_at)
);
```

---

## 🚀 Setup & Installation Guide

### Step 1: Open Terminal in Project Folder
Ensure your shell is positioned in the project root directory:
```powershell
cd "Road-Accident-Data-Analysis-System"
```

### Step 2: Install Required Python Packages
Install the required packages using pip:
```powershell
pip install -r requirements.txt
```

### Step 3: Configure Environment Credentials (`.env`)
Create your `.env` file from the provided `.env.example`:
```powershell
copy .env.example .env
```
Open `.env` and set your credentials:
```ini
# Database Configuration (MySQL or SQLite fallback)
DB_TYPE=mysql
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_actual_mysql_password
DB_NAME=accident_analysis_db

# Initial Administrator Account (Auto-created on first run if missing)
ADMIN_NAME=System Administrator
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=your_strong_admin_password

# Gmail SMTP Configuration for 6-Digit Email OTP Verification
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=yourgmail@gmail.com
MAIL_PASSWORD=your_gmail_app_password

# Flask Application Settings
SECRET_KEY=road_accident_mini_project_secret_key_2026
FLASK_DEBUG=False
PORT=5000
```

> **Gmail App Password Instructions:**
> 1. Go to your Google Account Settings -> **Security**.
> 2. Enable **2-Step Verification** (if not already enabled).
> 3. Search for **App passwords** in the top search bar.
> 4. Create a new App Password named `AccidentRadar` and paste the generated 16-character code into `MAIL_PASSWORD`.

### Step 4: Run the Application Server
Start the Flask development server:
```powershell
python app.py
```
Open your web browser and navigate to:
```
http://localhost:5000
```

### Step 5: Run Verification Test Suites
Run the automated test suites to verify that both the analytical system and authentication work flawlessly:
```powershell
# 1. Complete Web System Verification Suite
python test_app.py

# 2. Authentication, OTP, and Role-Based Access Control Test Suite
python test_auth.py
```

---

## 🖥️ System Modules & Features

### 1. Dashboard (`/dashboard`)
- **Key Performance Indicators (KPIs):** Total recorded accidents, Minor accidents count and percentage, Serious injury count and percentage, Fatal incident count and percentage.
- **NumPy Parametric Stats:** Mean accidents per calendar month ($\mu$), Median ($Q_2$), Standard Deviation ($\sigma$), and Interquartile Range ($IQR$).
- **Dynamic Matplotlib Charts:**
  - Annual trendlines categorized by injury severity.
  - Donut chart showing proportional severity distribution.
  - 24-Hour Diurnal accident curve showing peak commuter rush hours.

### 2. Accident Records Management (`/records`)
- **Working CRUD Operations:**
  - **Create:** Add new accident with validation of region, road name, datetime, vehicle type, and severity.
  - **Read:** Paginated data table with real-time multi-field search and filters.
  - **Update:** Asynchronous pre-population of modal dialog via `/api/record/<id>` and instant database commit.
  - **Delete:** Safe confirmation modal and relational database cleanup.
- **Multi-Field Search & Reset Filters:**
  - Search across accident location, year, vehicle type, severity, and road name.
  - Dedicated **Reset Filters** button to clear active queries in one click.
  - Clear **"No matching records found"** display when queries return 0 results.
- **Batch CSV Ingestion:**
  - Drag-and-drop or file selector for standard `.csv` files.
  - Schema validation with error logging for rejected rows.
  - Downloadable sample CSV template link inside the import dialog.

### 3. Accident Statistical Analysis (`/analysis`)
- **Year-Wise Analysis:** Annual volume and longitudinal fatality rates.
- **Location-Wise Analysis:** Geographical corridors ranked by accident count and injury severity.
- **Vehicle Classification Analysis:** Vulnerability breakdown comparing Bikes, Cars, Buses, Trucks, Autos, and Others.
- **Time-Wise / Diurnal Analysis:** Morning (05:00-11:59), Afternoon (12:00-16:59), Evening (17:00-21:59), and Night (22:00-04:59).
- **Weather Impact Analysis:** Correlation between weather conditions and severity.

### 4. Reports & Exports (`/reports`)
- **Downloadable Enriched CSV:** Full dataset with extracted temporal attributes.
- **Downloadable Text Summary Dossier:** Formal academic text report with KPI summaries, statistical dispersion metrics, and governance disclosures.
- **High-Resolution Chart Downloads:** Individual PNG downloads for all generated Matplotlib charts at 130 DPI with anti-aliasing.

---

## 📸 Screenshots & Visual Interface

| Interface | View Description |
| :--- | :--- |
| **Analytical Dashboard** | Displays high-level KPIs, monthly mean and dispersion, longitudinal yearly trendlines, and diurnal 24-hour accident curves. |
| **Accident Records Table** | Paginated surveillance table with badge styling for vehicle types and severities, modal edit/delete actions, and filter toolbar. |
| **Add / Edit Modal Dialogs** | Responsive modal dialogs with form validation, date-time pickers, and dynamic field loading. |
| **Multi-Dimensional Analysis** | Cross-tabulation matrices and statistical breakdown by Year, Location, Vehicle, Time-of-Day, and Weather. |
| **Reports & Export Center** | Download hub for publication-quality charts (PNG), raw CSV datasets, and formatted executive summaries. |

> *To display screenshots on GitHub, capture screenshots of each view and place them in `docs/screenshots/` (e.g., `docs/screenshots/dashboard.png`).*

---

## 🔒 Security & Academic Integrity

1. **SQL Injection Prevention:** Every query in `database.py` uses parameterized queries (`%s`) where user inputs are passed strictly as literals.
2. **Credential Isolation:** Passwords and secret keys are loaded exclusively from `.env` via `python-dotenv`. `.env` is ignored in `.gitignore`.
3. **No Hardcoded Passwords:** Placeholder values only in `.env.example`.
4. **No PII:** Contains zero personal identifying information.
5. **Causation Notice:** Explicitly discloses that all analytical observations demonstrate statistical associations, not direct causation.

---

## 🎓 Viva / Presentation Questions & Answers

**Q1: Why did you use parameterized queries instead of string concatenation?**
> *Answer:* Parameterized queries ensure that user inputs are treated strictly as data parameters, never interpreted as executable SQL statements, completely preventing SQL Injection attacks.

**Q2: How does the system extract the accident year?**
> *Answer:* The year is automatically extracted from the `accident_datetime` field using Python's `datetime` module and MySQL's `YEAR()` function, eliminating redundant manual input.

**Q3: How are Matplotlib graphs displayed in the web browser?**
> *Answer:* Matplotlib's non-interactive `Agg` backend renders the figure in memory into a `BytesIO` buffer, which is returned by Flask's `send_file` endpoint as `image/png`. This avoids disk I/O and dynamically updates whenever filters change.

**Q4: What role does Pandas play in this system?**
> *Answer:* Pandas handles data aggregation, multi-level grouping (`groupby()`, `unstack()`), cross-tabulation, and feature engineering (extracting month, hour, day name, and diurnal categories).

**Q5: What descriptive statistics are calculated with NumPy?**
> *Answer:* NumPy is used to calculate the arithmetic mean ($\mu$), median, sample standard deviation ($\sigma$), and the Interquartile Range ($IQR$) of monthly accident frequencies.
