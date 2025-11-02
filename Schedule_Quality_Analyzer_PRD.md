# Product Requirements Document
## EPC Schedule Assessment & Analysis Application

---

| **Document Version** | 1.0 |
| **Date** | November 2, 2025 |
| **Product Name** | Schedule Quality Analyzer |
| **Tech Stack** | Streamlit, Python, Pocketbase, GitHub |

---

## 1. Executive Summary

The Schedule Quality Analyzer is a web-based application designed to automate the assessment and analysis of EPC project schedules against industry best practices. The application implements DCMA 14-Point Schedule Assessment and GAO Schedule Assessment Guide methodologies, providing project managers and schedulers with instant, data-driven insights into schedule quality, risks, and improvement opportunities.

### Key Benefits

- Automated compliance checking against 17+ industry-standard schedule metrics
- Real-time identification of schedule deficiencies and risks
- Intelligent recommendations for schedule enhancement
- Professional executive summary reports in DOCX and Excel formats
- Comparison analytics for tracking schedule quality improvements over time
- Multi-user access with role-based permissions

---

## 2. Project Background

EPC infrastructure projects require rigorous schedule management to ensure successful delivery. Manual schedule assessment is time-consuming, subjective, and prone to inconsistency. Industry frameworks such as DCMA 14-Point Assessment and GAO Schedule Assessment Guide provide objective criteria, but their manual application requires significant expertise and effort.

This application addresses the need for automated, consistent, and comprehensive schedule quality analysis that empowers project teams to proactively identify and mitigate schedule risks before they impact project delivery.

---

## 3. Problem Statement

### Current Challenges:

- Manual schedule assessment requires 8-16 hours per project
- Inconsistent application of best practices across projects and teams
- Delayed identification of schedule quality issues until problems escalate
- Lack of standardized reporting for stakeholder communication
- Difficulty tracking schedule quality improvements over time

---

## 4. Objectives

### Primary Objectives

1. Automate DCMA 14-Point and GAO Schedule Assessment workflows
2. Reduce schedule assessment time from hours to minutes
3. Provide actionable recommendations for schedule enhancement
4. Enable comparison analytics for before/after analysis
5. Generate professional reports suitable for client and stakeholder communication

### Secondary Objectives

- Establish a knowledge repository of schedule quality metrics across projects
- Support continuous improvement through trend analysis
- Facilitate team collaboration with multi-user access

---

## 5. Target Users

| **User Type** | **Role** | **Primary Needs** |
|---------------|----------|-------------------|
| **Project Schedulers** | Admin | Upload schedules, run analyses, generate reports, make improvements |
| **Project Managers** | Admin | Review KPIs, understand risks, track improvements |
| **Senior Leadership** | Viewer | View dashboards, access executive summaries, monitor portfolio health |
| **Clients / Owners** | Viewer | Review schedule quality, understand risks, verify compliance |

---

## 6. Features & Functional Requirements

### 6.1 User Authentication & Authorization

**Requirements:**

- Secure user registration and login functionality
- Two user roles: Admin and Viewer
- Admin role: Full access to upload, analyze, edit, and delete schedules
- Viewer role: Read-only access to dashboards and reports
- Session management with automatic timeout after 30 minutes of inactivity
- Password reset functionality

### 6.2 Schedule Data Import

**Requirements:**

- CSV file upload capability with drag-and-drop interface
- Parser for standard P6 schedule export format with the following columns:
  - Activity ID, Activity Status, WBS Code, At Completion Duration
  - Activity Name, Start, Finish, Free Float, Total Float
  - Predecessors, Predecessor Details, Successors, Successor Details
  - Primary Constraint, Activity Type, Duration Type
- Intelligent parsing of relationship lag notation (e.g., 'A21740: FF 10' = Finish-to-Finish with 10-day positive lag)
- Data validation and error reporting for malformed CSV files
- Storage of uploaded schedules in Pocketbase with metadata (project name, upload date, uploader)
- Version control for multiple schedule uploads of the same project
- Ability to view and compare historical schedule versions

### 6.3 Schedule Assessment & Analysis Engine

The application shall implement automated analysis based on DCMA 14-Point Assessment and GAO Schedule Assessment Guide best practices.

#### 6.3.1 Logic and Network Integrity Checks

- **Negative Lag Detection:** Identify and count all negative lags (leads); target = 0
- **Positive Lag Analysis:** Calculate percentage of relationships with positive lags; target ≤ 5%
- **Hard Constraint Analysis:** Count activities with mandatory start/finish dates; target ≤ 10%
- **Missing Logic Detection:** Identify activities without predecessors or successors
- **Open-End Activities:** List activities with missing predecessor or successor relationships

#### 6.3.2 Schedule Realism Checks

- **Long Duration Activities:** Identify activities exceeding 20 working days; flag those exceeding 5 months
- **Average Activity Duration:** Calculate mean duration; benchmark 10-20 days typical
- **High Float Analysis:** Identify activities with excessive total float (>50% of project duration)
- **Float Ratio Calculation:** Average float divided by average remaining duration; target 0.5-1.5
- **Activity Distribution Analysis:** Calculate activities per month; flag unbalanced distribution

#### 6.3.3 Execution Readiness Assessment

- **Resource Assignment Check:** Identify incomplete activities without resource assignments
- **Milestone Validation:** Verify start/finish milestones have zero duration
- **Activity Type Analysis:** Categorize activities by type (Task Dependent, Resource Dependent, etc.)

#### 6.3.4 Performance Metrics Calculation

- **Critical Path Length Index (CPLI):** (Critical Path + Total Float) / Critical Path; target ≥ 0.95
- **Baseline Execution Index (BEI):** Tasks Completed / Tasks Planned; target ≥ 0.95
- **Schedule Performance Index:** Ratio of earned value to planned value

#### 6.3.5 Intelligent Recommendations Engine

The system shall provide prioritized, actionable recommendations:

- **High Priority:** Negative lags, missing logic, excessive constraints, CPLI < 0.90
- **Medium Priority:** Long duration activities, high float, resource gaps, CPLI 0.90-0.95
- **Low Priority:** Excessive positive lags, activity distribution imbalances

Each recommendation includes:
- Issue description
- Impact assessment
- Suggested action
- Affected activities list

### 6.4 Dashboards & Visualizations

#### 6.4.1 Overview Dashboard

- Schedule Health Score: Composite metric (0-100) based on DCMA compliance
- Key Metrics Summary: CPLI, BEI, Total Activities, Critical Path Duration
- Issues Summary: Count of high/medium/low priority findings
- Compliance Gauge Chart: Visual indicator of DCMA 14-Point compliance

#### 6.4.2 Detailed Metrics Dashboard

- Logic Quality Metrics: Bar charts for negative lags, positive lags, hard constraints, missing logic
- Duration Analysis: Histogram of activity durations with threshold indicators
- Float Distribution: Box plot showing float distribution and outliers
- Activity Status Breakdown: Pie chart of Not Started / In Progress / Completed
- WBS Analysis: Tree map or sunburst chart of activities by WBS code

#### 6.4.3 Comparison Dashboard

- Side-by-side metric comparison for multiple schedule versions
- Trend charts showing metric improvements over time
- Before/After analysis highlighting improvements and remaining issues
- Delta calculations showing percentage improvements in key metrics

#### 6.4.4 Activity Detail View

- Filterable, sortable data table of all activities
- Search functionality by Activity ID, Activity Name, WBS Code
- Issue flagging with color-coded indicators
- Export to CSV functionality for filtered results

### 6.5 Report Generation & Export

#### 6.5.1 Executive Summary Report (DOCX)

Professional Word document containing:

- Cover page with project name, analysis date, schedule health score
- Executive summary section with key findings and overall assessment
- DCMA 14-Point compliance checklist with pass/fail status
- Critical metrics dashboard: CPLI, BEI, float ratio, constraint percentage
- Issues summary table categorized by priority level
- Detailed findings section with descriptions and affected activities
- Recommendations section with prioritized action items
- Appendix with methodology explanation and metric definitions

#### 6.5.2 Detailed Analysis Report (Excel)

Multi-sheet Excel workbook containing:

- **Summary sheet:** All key metrics and compliance indicators
- **Issues sheet:** Complete list of identified issues with severity and recommendations
- **Activities sheet:** Full activity list with calculated metrics
- **Logic sheet:** Predecessor/successor relationships with lag analysis
- **Metrics sheet:** Detailed breakdown of all calculated metrics
- **Charts sheet:** Embedded visualizations (histograms, bar charts, pie charts)

#### 6.5.3 Export Functionality

- One-click export buttons for both DOCX and Excel formats
- Automatic filename generation with project name and date
- Download history tracking for audit purposes

---

## 7. Technical Architecture

### 7.1 Technology Stack

| **Component** | **Technology** |
|---------------|----------------|
| **Frontend** | Streamlit 1.28+ |
| **Backend Language** | Python 3.11+ |
| **Database** | Pocketbase (SQLite-based) |
| **Data Processing** | Pandas, NumPy |
| **Visualization** | Plotly, Altair, Matplotlib |
| **Report Generation** | python-docx, openpyxl |
| **Authentication** | Pocketbase Auth, Streamlit-Authenticator |
| **Deployment** | Streamlit Community Cloud |
| **Version Control** | GitHub |

### 7.2 Application Architecture

The application follows a modular, three-tier architecture:

#### Presentation Layer (Streamlit)

- User interface components (pages, forms, charts, tables)
- Session state management
- File upload/download handlers

#### Business Logic Layer (Python Modules)

- CSV parser and data validator
- Schedule analysis engine (DCMA metrics calculator)
- Recommendations engine
- Report generator (DOCX/Excel)
- Comparison analytics module

#### Data Layer (Pocketbase)

- User authentication and authorization
- Schedule data storage
- Analysis results caching
- Audit log for user actions

---

## 8. Data Model

Pocketbase collections and relationships:

### 8.1 Users Collection

- `id` (auto-generated)
- `email` (unique, required)
- `username` (unique, required)
- `password` (hashed)
- `role` (enum: 'admin', 'viewer')
- `created`, `updated` (timestamps)

### 8.2 Projects Collection

- `id` (auto-generated)
- `project_name` (required)
- `project_code` (unique)
- `description` (text)
- `created_by` (relation to Users)

### 8.3 Schedules Collection

- `id` (auto-generated)
- `project_id` (relation to Projects)
- `version_number` (integer, auto-increment per project)
- `schedule_data` (JSON, full parsed CSV data)
- `file_name` (original CSV filename)
- `upload_date` (timestamp)
- `uploaded_by` (relation to Users)
- `analysis_status` (enum: 'pending', 'complete', 'error')

### 8.4 Analysis_Results Collection

- `id` (auto-generated)
- `schedule_id` (relation to Schedules)
- `metrics` (JSON, all calculated DCMA metrics)
- `issues` (JSON, array of identified issues with priority)
- `recommendations` (JSON, array of recommendations)
- `health_score` (float, 0-100)
- `analysis_date` (timestamp)

### 8.5 Audit_Log Collection

- `id` (auto-generated)
- `user_id` (relation to Users)
- `action_type` (enum: 'upload', 'analyze', 'export', 'delete')
- `resource_id` (generic reference)
- `details` (JSON)
- `timestamp` (auto-generated)

---

## 9. User Experience & Interface Design

### 9.1 Design Principles

- Professional EPC industry aesthetic with clean, modern layout
- Intuitive navigation with minimal training required
- Mobile-responsive design (tablet minimum, desktop optimized)
- Color scheme: Blues and grays for professionalism; red/yellow/green for status indicators
- Consistent use of icons and visual cues

### 9.2 Page Structure

#### Login Page

- Centered login form with username/password
- Links for password reset and new user registration (if enabled)

#### Home/Dashboard Page

- Top navigation bar with logo, user profile, logout
- Sidebar navigation: Home, Projects, Upload, Analysis, Reports, Settings
- Main content area with project list or welcome message

#### Upload Page

- Drag-and-drop file upload zone
- Project selection dropdown or new project creation form
- Upload progress indicator and validation feedback

#### Analysis Dashboard Page

- Schedule selector dropdown
- Three-column layout: Overview metrics | Key issues | Recommendations
- Tabs for different dashboard views (Overview, Metrics, Comparison, Activities)
- Export buttons in top-right corner

#### Reports Page

- List of generated reports with download links
- Filters by date range, project, report type

---

## 10. Security & Authentication

### 10.1 Authentication Requirements

- Secure password hashing using bcrypt or argon2
- Password complexity requirements: minimum 8 characters, uppercase, lowercase, number
- Session token-based authentication with 30-minute inactivity timeout
- Secure password reset via email verification

### 10.2 Authorization & Access Control

| **Feature** | **Admin** | **Viewer** |
|-------------|-----------|------------|
| Upload Schedule | ✓ | ✗ |
| Run Analysis | ✓ | ✗ |
| View Dashboards | ✓ | ✓ |
| Export Reports | ✓ | ✓ |
| Delete Schedule | ✓ | ✗ |
| Manage Users | ✓ | ✗ |

### 10.3 Data Security

- HTTPS enforcement for all connections
- Encrypted storage of sensitive data in Pocketbase
- Input validation and sanitization to prevent injection attacks
- File upload restrictions: CSV only, maximum 50MB file size
- Rate limiting on API endpoints to prevent abuse

### 10.4 Audit & Compliance

- Comprehensive audit logging of all user actions
- Timestamped records of schedule uploads, analyses, exports, and deletions
- Admin dashboard for reviewing audit logs

---

## 11. Deployment & DevOps

### 11.1 Deployment Strategy

- Primary hosting: Streamlit Community Cloud (free tier)
- Source code repository: GitHub private repository
- Continuous deployment: Automatic deployment on push to main branch
- Pocketbase: Self-hosted on lightweight VPS or PaaS (e.g., Railway, Fly.io)

### 11.2 Configuration Management

- Environment variables for sensitive configuration (database URLs, API keys)
- Streamlit secrets management for secure credential storage
- Separate configurations for development and production environments

### 11.3 Monitoring & Maintenance

- Application health monitoring via Streamlit Cloud dashboard
- Error logging and alerting for critical failures
- Regular database backups (daily snapshots of Pocketbase)
- Scheduled maintenance windows for updates (communicated to users in advance)

---

## 12. Success Metrics

### 12.1 Performance Metrics

- CSV parsing and upload: <10 seconds for typical schedule (1000-1500 activities)
- Schedule analysis execution: <30 seconds for full DCMA assessment
- Dashboard rendering: <5 seconds for all visualizations
- Report generation: <15 seconds for DOCX and Excel export

### 12.2 User Adoption Metrics

- Number of active users (monthly active users target: 20+ within first quarter)
- Number of schedules analyzed (target: 50+ schedules in first 3 months)
- Report export frequency (indicator of value delivery)
- User session duration (target: >10 minutes average, indicating engagement)

### 12.3 Business Impact Metrics

- Time savings: Reduce schedule assessment from 8-16 hours to <1 hour (>90% reduction)
- Schedule quality improvement: Track average health score increase across projects
- User satisfaction: Target Net Promoter Score (NPS) >70
- Error reduction: Decrease schedule-related project delays by early risk identification

---

## 13. Development Approach

This application will be developed using Claude Code AI with an iterative, feature-driven approach. The development will proceed in phases, with each phase delivering working functionality that can be tested and refined before moving to the next phase.

### Development Phases

#### Phase 1: Foundation (Weeks 1-2)

- Set up GitHub repository and project structure
- Implement basic Streamlit application framework
- Configure Pocketbase and create data model
- Implement user authentication (login/logout)
- Create CSV parser and data validation module

#### Phase 2: Core Analysis Engine (Weeks 3-4)

- Implement DCMA 14-Point metrics calculation
- Build logic analysis module (negative lags, positive lags, constraints)
- Develop duration and float analysis algorithms
- Calculate CPLI, BEI, and other performance indices
- Create recommendations engine with prioritization logic

#### Phase 3: Dashboards & Visualizations (Weeks 5-6)

- Build overview dashboard with health score and key metrics
- Create detailed metrics visualizations (charts, graphs, tables)
- Implement comparison dashboard for version analysis
- Develop activity detail view with filtering and search

#### Phase 4: Report Generation (Weeks 7-8)

- Implement DOCX executive summary report generator
- Build Excel detailed analysis report with multiple sheets
- Add export functionality with download buttons
- Create report management interface

#### Phase 5: Polish & Deployment (Weeks 9-10)

- Refine UI/UX based on testing feedback
- Implement error handling and user feedback mechanisms
- Add help documentation and tooltips
- Deploy to Streamlit Community Cloud
- Conduct user acceptance testing and final refinements

---

## 14. Future Enhancements

The following features are planned for future releases after initial deployment:

### Phase 2 Enhancements (3-6 months post-launch)

1. Monte Carlo Schedule Risk Analysis: Probabilistic assessment with confidence intervals
2. Critical Path Visualization: Interactive network diagrams and Gantt charts
3. What-If Scenario Analysis: Test impact of activity duration changes
4. Automated Schedule Improvement: AI-powered suggestions for logic optimization
5. Email Notifications: Alerts for schedule health degradation

### Phase 3 Enhancements (6-12 months post-launch)

1. Direct P6 XER File Import: Eliminate CSV export step
2. Resource Loading Analysis: Evaluate resource allocation and leveling
3. Custom Metrics Configuration: Allow users to define organization-specific thresholds
4. Portfolio Dashboard: Multi-project health monitoring
5. API Integration: RESTful API for third-party tool integration
6. Mobile Application: iOS/Android apps for on-site schedule reviews

### Advanced Features (12+ months)

1. Machine Learning Predictions: Forecast schedule health trends
2. Natural Language Query: Ask questions about schedule in plain English
3. Collaborative Features: Team annotations and discussion threads
4. Integration with BIM/4D Tools: Link schedule to 3D models

---

## 15. Assumptions & Constraints

### Assumptions

- Users have basic understanding of project scheduling concepts and terminology
- Schedules are exported from Primavera P6 in the specified CSV format
- Users have stable internet connection for cloud-based application access
- Typical schedule size: 500-2000 activities (application will handle up to 10,000 activities)
- Users require reports in English language only for initial version

### Constraints

- Streamlit Community Cloud limitations: 1GB RAM, limited CPU resources
- Development by single developer using AI assistance (Claude Code)
- No budget for premium third-party services or APIs
- Must use free/open-source technologies for MVP
- 10-week development timeline for initial release

---

## 16. Risks & Mitigation Strategies

| **Risk** | **Impact** | **Mitigation** |
|----------|-----------|----------------|
| **CSV format variations** | Parser fails on non-standard exports | Implement flexible parser with format detection; provide clear export instructions |
| **Performance with large schedules** | Slow analysis for 5000+ activity schedules | Optimize algorithms using vectorized pandas operations; implement caching; show progress indicators |
| **Pocketbase downtime** | Users unable to access data or authenticate | Daily backups; health monitoring; graceful error messages; fallback to read-only mode |
| **Low user adoption** | Application not used after launch | Conduct user training sessions; create demo videos; gather early feedback; ensure intuitive UX |
| **Scope creep** | Development timeline extends beyond 10 weeks | Strictly adhere to MVP feature set; defer enhancements to Phase 2; maintain feature backlog |

---

## 17. Glossary

| **Term** | **Definition** |
|----------|----------------|
| **BEI** | Baseline Execution Index: Ratio of completed tasks to planned tasks; measures schedule adherence |
| **CPLI** | Critical Path Length Index: Measures schedule compression; calculated as (Critical Path + Total Float) / Critical Path |
| **DCMA** | Defense Contract Management Agency: Developed the 14-Point Schedule Assessment framework |
| **EPC** | Engineering, Procurement, Construction: Integrated project delivery approach for infrastructure projects |
| **Float** | Schedule flexibility: Amount of time an activity can be delayed without impacting project completion |
| **GAO** | Government Accountability Office: Published Schedule Assessment Guide with 10 best practices |
| **Hard Constraint** | Fixed start or finish date that overrides logical relationships; reduces schedule flexibility |
| **Lag** | Time delay between predecessor and successor activities; positive lag = delay, negative lag (lead) = overlap |
| **P6** | Primavera P6: Industry-standard project scheduling software used in EPC projects |
| **WBS** | Work Breakdown Structure: Hierarchical decomposition of project scope into manageable components |

---

**— End of Document —**
