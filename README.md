# Payroll Manager - Desktop & WhatsApp Management System

A production-quality standalone Python desktop application that merges employee payroll parsing, synchronization, ReportLab Form VIII-C PDF slip generation, and rate-limited WhatsApp messaging (both Text template and Media API PDF slip delivery) into a single unified desktop interface.

Built using **Python 3.12+**, **PySide6 (Qt)**, **SQLAlchemy 2.x**, **SQLite**, and **ReportLab**.

---

## Key Features

1. **🏠 Operational Dashboard**: Displays current payroll month stats, total employees, PDFs generated, pending slips, text messages sent, PDF messages sent, failed messages, and the current retry queue. Also features a scrolling real-time activity log.
2. **📥 Excel Upload Preview & Commit**: Green/Red validation highlight grids parsing the standard 22-column payroll Excel sheet. Performs phone check, salary calculations, and gross-to-net wage mathematical alignment before committing transactions to SQLite.
3. **🔄 Automatic Employee & Payroll Sync**: Auto-creates or updates permanent Employee profiles on Workman ID. Merges and overwrites existing payroll monthly runs when updated files are imported.
4. **📄 Automatic Form VIII-C PDF Regeneration**: Generates or regenerates government compliance wage slips locally (`GeneratedPdfs/<Year>/<Month>/<pdf_uuid>.pdf`) when wages variables change. Includes an **embedded PDF viewer** dialog.
5. **💬 WhatsApp Text template distribution**: Delivers template wage slips respecting the Token Bucket rate limiter, adaptive backoffs, and Graph API requirements.
6. **📎 WhatsApp PDF document delivery**: Uploads generated PDF files to Meta's Media API, retrieves the media ID, and sends document messages using Meta's approved WhatsApp Document Template.
7. **⚙️ Persistence Settings**: Categorized settings interface storing Meta Graph tokens, template names, rate limits (MPS), custom folder paths, and retry delays inside SQLite.
8. **📜 Audit log trails**: Searchable transmission grids masking sensitive employee data (phone numbers, bank accounts, UAN, salaries) and exporting rows directly to CSV files.

---

## Screenshots

*(Insert screenshots of your running application here)*
- **Dashboard View**: Sleek dark theme featuring operational cards and recent activity logs.
- **Upload Payroll**: Red/green highlighting showing calculation audits.
- **Wage Slips**: Excel-like spreadsheet table layout with detailed large action buttons.
- **Settings Form**: Secure configuration fields for Meta credentials and directory structures.

---

## Technologies Used

- **GUI Framework**: PySide6 (Qt for Python)
- **Database ORM**: SQLAlchemy 2.x
- **Local Database**: SQLite (with WAL mode enabled)
- **PDF Generation**: ReportLab
- **Excel Processing**: openpyxl, pandas
- **Network & APIs**: requests (Meta Graph API & WhatsApp Cloud API)
- **Validation**: Google phonenumbers, custom regex filters
- **Testing**: unittest, pytest

---

## Folder Structure

```
python-payroll/
├── main.py                     # Primary Application Entry Point
├── requirements.txt            # Package Dependencies
├── README.md                   # Setup Documentation
├── scripts/
│   ├── generate_sample_excel.py# Test spreadsheet generation utility
│   └── inspect_meta_template.py# Meta Graph template introspection debugger
├── database/
│   ├── db.py                   # SQLAlchemy Engine & Session Setup
│   └── models.py               # Consolidated Employee, PayrollRecord, and Setting tables
├── services/
│   ├── payroll_service.py      # Spreadsheet previews, sync commits, deletions
│   ├── pdf_service.py          # ReportLab Form VIII-C engine & folder directories
│   └── whatsapp_service.py     # Cloud API sends, Media API uploads, rate limiter, retries
├── settings/
│   └── settings_manager.py     # Key-value loaders/savers in SQLite
├── utils/
│   ├── excel_parser.py         # 22-column sheet reader
│   ├── phone_utils.py          # Google phonenumbers parsing & E.164 normalization
│   ├── rate_limiter.py         # Token Bucket rate limiter
│   └── logger_config.py        # Centralized logger with privacy PII masking filters
├── workers/
│   └── qthreads.py             # QThread background worker threads
├── ui/
│   ├── main_window.py          # Navigation frame coordinating tabs
│   ├── style.py                # Premium dark QSS stylesheet
│   ├── dashboard_tab.py        # Status cards list
│   ├── upload_tab.py           # Parsing preview and commit buttons
│   ├── wageslips_tab.py        # History table list, previewer, regenerator
│   ├── send_text_tab.py        # Text sending checklists
│   ├── send_pdf_tab.py         # PDF media sending checklists
│   ├── pdf_preview.py          # Embedded QPdfView popup
│   ├── settings_tab.py         # Credentials and test connections forms
│   └── logs_tab.py             # Masked delivery log lists
└── tests/
    ├── test_parser.py          # Spreadsheet parser assertions
    ├── test_pdf.py             # ReportLab builder assertions
    └── test_whatsapp.py        # API mocks assertions
```

---

## Installation & Setup

### 1. Create a Virtual Environment
It is recommended to run the project in a virtual environment to manage dependencies:
```bash
# Create the environment
python3 -m venv venv

# Activate on macOS/Linux:
source venv/bin/activate

# Activate on Windows (Command Prompt):
venv\Scripts\activate.bat

# Activate on Windows (PowerShell):
.\venv\Scripts\Activate.ps1
```

### 2. Install Requirements
Install all dependencies listed in the requirements file:
```bash
pip install -r requirements.txt
```

### 3. Generate Sample Payroll Data
To test the spreadsheet parsing and validation grid, generate a sample Excel spreadsheet with mock employee records:
```bash
python scripts/generate_sample_excel.py
```
This outputs `sample_payroll.xlsx` in the root folder containing both mathematically valid rows and intentionally flagged invalid rows (for checking red highlights).

### 4. Run the Application
Execute the primary entry script:
```bash
python main.py
```

### 5. Running Tests
Run the unit test suite:
```bash
python -m unittest discover tests
```

---

## Configuration & WhatsApp Cloud API Setup

### Application Storage
On startup, the system automatically initializes a sqlite database and configures log rotation inside a system config directory (e.g. `~/.config/DesktopPayrollSystem` on macOS/Linux or `%APPDATA%/DesktopPayrollSystem` on Windows). 

### Setup Meta Credentials
In the **Settings** tab inside the application:
1. Input your Meta **Access Token** and **Phone Number ID**.
2. Input your **Business Account ID**.
3. Set the **Template Name** (e.g., `temp1` or `wageslip`) and matching language code (`en`).
4. Click **Test Connection** to execute a validation check. The app queries Meta's API and returns connection success/failure diagnostics.

### Expected Template Schema
The WhatsApp template must be configured under Meta Business Manager with **21 Named body variables** mapped in the following exact order:
1. `month_year`
2. `establishment`
3. `principal_employer`
4. `address`
5. `employee_name`
6. `workman_id`
7. `guardian_name`
8. `designation`
9. `uan`
10. `bank_account`
11. `wage_period`
12. `attendance`
13. `basic`
14. `da`
15. `allowances`
16. `gross_wages`
17. `pf`
18. `esi`
19. `other_deductions`
20. `net_wages`
21. `issue_date`

---

## Known Limitations

- **Meta Media Lifetimes**: PDFs uploaded to Meta's Cloud Media API are only stored by Meta for 30 days. The application uploads each unique PDF individually during dispatch.
- **Internet Dependency**: Sending WhatsApp messages and verifying credentials requires an active internet connection to contact Meta Graph servers.
- **PDF Viewer Fallback**: The native embedded QPdfView widget depends on QtPdf plugins compiled in your PySide6 installation. If unavailable on your platform build, it safely falls back to launching the operating system's default viewer.

---

## Future Roadmap

- **Local PDF Encryption**: Encrypt generated wage slip PDFs with passwords dynamically derived from the employee's bank account numbers or birth years.
- **Auto-Retry Scheduler**: Introduce a background service daemon to process the message retry queue periodically even when the desktop interface is closed.
- **Custom PDF Templating**: Build an in-app drag-and-drop editor allowing employers to customize PDF slip formats without code changes.
- **Sync Connectors**: Build direct integrations with standard HR systems (like BambooHR or Workday) for direct API synchronizations.

---

## License

This project is open-source and licensed under the [MIT License](LICENSE).

