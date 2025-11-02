# Schedule Quality Analyzer

> **Automated EPC Schedule Assessment & Analysis Application**

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![Streamlit](https://img.shields.io/badge/streamlit-1.28%2B-red.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## 📋 Overview

The **Schedule Quality Analyzer** is a web-based application designed to automate the assessment and analysis of EPC (Engineering, Procurement, Construction) project schedules against industry best practices. It implements **DCMA 14-Point Schedule Assessment** and **GAO Schedule Assessment Guide** methodologies, providing project managers and schedulers with instant, data-driven insights into schedule quality, risks, and improvement opportunities.

## ✨ Key Features

- ✅ **Automated Schedule Analysis** - DCMA 14-Point and GAO compliance checking
- 📊 **Interactive Dashboards** - Real-time metrics with visualizations
- 📄 **Professional Reports** - Generate DOCX and Excel reports
- 🔍 **Schedule Comparison** - Track quality improvements across versions
- 👥 **Multi-User Access** - Role-based permissions (Admin/Viewer)
- 💡 **Smart Recommendations** - Prioritized, actionable improvement suggestions
- 🎯 **Health Score** - Composite 0-100 metric for schedule quality

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- pip package manager
- Git

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/drogoXX/ScheduleAss.git
cd ScheduleAss
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Run the application**
```bash
streamlit run app.py
```

4. **Access the application**
- Open your browser to `http://localhost:8501`
- Login with demo credentials (see below)

### Demo Credentials

**Admin Account:**
- Username: `admin`
- Password: `admin123`

**Viewer Account:**
- Username: `viewer`
- Password: `viewer123`

## 📖 User Guide

### Uploading a Schedule

1. Navigate to **Upload Schedule** page
2. Select an existing project or create a new one
3. Upload your P6 CSV export file
4. Click **Upload and Analyze**
5. Wait for analysis to complete (10-30 seconds)

### Viewing Analysis

1. Go to **Analysis Dashboard**
2. Select a schedule from the dropdown
3. Explore different tabs:
   - **Overview**: Health score and key metrics
   - **Detailed Metrics**: In-depth analysis with charts
   - **Issues**: Identified problems by severity
   - **Recommendations**: Prioritized improvement actions
   - **Activities**: Searchable activity list

### Generating Reports

1. Visit **Reports** page
2. Select a schedule
3. Choose report type:
   - **DOCX**: Executive summary for stakeholders
   - **Excel**: Detailed analysis for technical teams
4. Click **Generate** and download

### Comparing Schedules

1. Navigate to **Comparison** page
2. Select two schedule versions
3. View side-by-side metrics
4. Analyze improvements or regressions

## 🏗️ Project Structure

```
ScheduleAss/
├── app.py                          # Main application entry point
├── requirements.txt                # Python dependencies
├── .streamlit/
│   └── config.toml                # Streamlit configuration
├── src/
│   ├── auth/
│   │   └── auth_manager.py        # Authentication logic
│   ├── parsers/
│   │   └── schedule_parser.py     # CSV parser for P6 exports
│   ├── analysis/
│   │   ├── dcma_analyzer.py       # DCMA metrics calculator
│   │   ├── metrics_calculator.py  # CPLI, BEI, health score
│   │   └── recommendations.py     # Recommendations engine
│   ├── database/
│   │   └── db_manager.py          # Data storage manager
│   ├── reports/
│   │   ├── docx_generator.py      # DOCX report generator
│   │   └── excel_generator.py     # Excel report generator
│   └── utils/
│       └── helpers.py             # Utility functions
├── pages/
│   ├── 1_Upload_Schedule.py       # Upload interface
│   ├── 2_Analysis_Dashboard.py    # Main dashboard
│   ├── 3_Comparison.py            # Schedule comparison
│   ├── 4_Reports.py               # Report generation
│   └── 5_Settings.py              # Settings and profile
├── data/
│   └── sample_schedule.csv        # Sample P6 export
└── README.md                      # This file
```

## 📊 Supported CSV Format

The application expects Primavera P6 CSV exports with the following columns:

### Required Columns
- Activity ID
- Activity Name
- Activity Status
- Start
- Finish
- Total Float
- Duration Type

### Optional Columns (Recommended)
- WBS Code
- At Completion Duration
- Free Float
- Predecessors / Predecessor Details
- Successors / Successor Details
- Primary Constraint
- Activity Type
- Resource Names

### Example P6 Export Settings

When exporting from P6:
1. File → Export → Spreadsheet
2. Select "Activity" layout
3. Include all columns listed above
4. Export as CSV format

## 🔍 Analysis Metrics

### DCMA 14-Point Assessment

| Metric | Description | Target |
|--------|-------------|--------|
| **Negative Lags** | Activities with lead relationships | 0 |
| **Positive Lags** | Percentage of relationships with lags | ≤5% |
| **Hard Constraints** | Activities with mandatory dates | ≤10% |
| **Missing Logic** | Activities without predecessors/successors | 0 |
| **Long Durations** | Activities exceeding 20 days | Minimize |
| **High Float** | Excessive total float activities | Review |

### Performance Indices

- **CPLI (Critical Path Length Index)**
  - Formula: (Critical Path + Total Float) / Critical Path
  - Target: ≥ 0.95
  - Measures schedule compression risk

- **BEI (Baseline Execution Index)**
  - Formula: Completed Tasks / Planned Tasks
  - Target: ≥ 0.95
  - Measures schedule adherence

- **Health Score**
  - Composite metric (0-100)
  - Based on DCMA compliance
  - Ratings: Excellent (90-100), Good (75-89), Fair (60-74), Poor (40-59), Critical (0-39)

## 🔐 Security & Authentication

### User Roles

| Role | Permissions |
|------|-------------|
| **Admin** | Upload schedules, run analysis, generate reports, delete data, manage users |
| **Viewer** | View dashboards, access reports (read-only) |

### Session Management

- 30-minute inactivity timeout
- Password-based authentication
- Session state isolation
- Audit logging for all actions

## 🛠️ Technology Stack

| Component | Technology |
|-----------|-----------|
| **Frontend** | Streamlit 1.28+ |
| **Backend** | Python 3.11+ |
| **Database** | Session-based (upgradeable to Pocketbase) |
| **Data Processing** | Pandas, NumPy |
| **Visualization** | Plotly, Altair, Matplotlib |
| **Reports** | python-docx, openpyxl |
| **Authentication** | Streamlit Session State |

## 📈 Performance

- **CSV Parsing**: <10 seconds for 1000-1500 activities
- **Analysis Execution**: <30 seconds for full DCMA assessment
- **Dashboard Rendering**: <5 seconds for all visualizations
- **Report Generation**: <15 seconds for DOCX and Excel

## 🚧 Troubleshooting

### Common Issues

**"Missing required columns" error**
- Verify P6 export includes all required fields
- Check column names match expected format

**"Failed to parse CSV" error**
- Ensure file is valid CSV format
- Remove special characters or formatting issues
- Try re-exporting from P6

**Analysis takes too long**
- Large schedules (>5000 activities) may take longer
- Check system resources (RAM, CPU)
- Try with smaller schedule first

**Login not working**
- Verify correct username/password
- Try refreshing the page
- Clear browser cache

## 🔄 Deployment

### Streamlit Community Cloud

1. Push code to GitHub repository
2. Visit [streamlit.io/cloud](https://streamlit.io/cloud)
3. Connect your GitHub account
4. Deploy from repository
5. Configure secrets (if needed)

### Local Deployment

```bash
# Production mode
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

### Docker Deployment (Coming Soon)

```dockerfile
# Dockerfile example
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["streamlit", "run", "app.py"]
```

## 🗺️ Roadmap

### Phase 1 ✅ (Current)
- ✅ Basic authentication
- ✅ CSV parser
- ✅ DCMA analysis engine
- ✅ Dashboards and visualizations
- ✅ Report generation (DOCX & Excel)
- ✅ Schedule comparison

### Phase 2 🚧 (Planned)
- [ ] Pocketbase integration
- [ ] Advanced user management
- [ ] Monte Carlo risk analysis
- [ ] Critical path visualization
- [ ] Email notifications
- [ ] Custom metric thresholds

### Phase 3 🔮 (Future)
- [ ] Direct XER file import
- [ ] Resource loading analysis
- [ ] Portfolio dashboard
- [ ] RESTful API
- [ ] Mobile app
- [ ] Machine learning predictions

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📧 Contact

For questions, issues, or suggestions:

- **GitHub Issues**: [Create an issue](https://github.com/drogoXX/ScheduleAss/issues)
- **Email**: [Your email]
- **Documentation**: See in-app help sections

## 🙏 Acknowledgments

- **DCMA** - For the 14-Point Schedule Assessment framework
- **GAO** - For Schedule Assessment Guide best practices
- **Streamlit** - For the amazing web framework
- **Community** - For feedback and contributions

## 📚 References

- [DCMA 14-Point Assessment](https://www.dcma.mil/Portals/31/Documents/Policy/DCMA-INST-318.pdf)
- [GAO Schedule Assessment Guide](https://www.gao.gov/products/gao-16-89g)
- [Primavera P6 Documentation](https://docs.oracle.com/cd/E80480_01/)
- [Streamlit Documentation](https://docs.streamlit.io/)

---

**Built with ❤️ for EPC Project Teams**

*Version 1.0.0 - November 2025*
