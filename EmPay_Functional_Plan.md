# EmPay Functional Plan

## 1. Project Summary

**Product Name:** EmPay - Smart Human Resource Management System  
**Type:** Web-based HRMS for startups, institutions, and SMEs  
**Goal:** Build a reliable system that connects employee management, attendance, leave, payroll, and analytics in one platform.

EmPay should help organizations reduce manual HR work, improve transparency, and automate employee-related workflows. The system must support four roles:

- Admin
- Employee
- HR Officer
- Payroll Officer

The most important business flow in this problem statement is:

`Employees -> Attendance -> Leave/Approvals -> Payroll -> Payslip/Reports -> Dashboard Analytics`

## 2. Problem Understanding

The statement asks for a working HRMS with:

- User registration and login
- Role-based access
- Editable profiles
- Attendance marking and log viewing
- Leave application and approval workflows
- Payroll generation using attendance and approved leave data
- Payslips and monthly reports
- Dashboard summaries and HR analytics

The challenge is not only CRUD. The system must show business relationships between modules, especially how attendance and approved time-off affect payroll and reporting.

## 3. Business Objectives

- Centralize employee, attendance, leave, and payroll records
- Reduce spreadsheet/manual dependency
- Give employees self-service access to their own information
- Give HR and payroll teams controlled operational access
- Provide admins a full system-wide view
- Generate simple but accurate payroll and reporting outputs

## 4. Scope

### In Scope

- Authentication and authorization
- Employee profile management
- Attendance marking and tracking
- Leave type allocation and balance tracking
- Leave approval/rejection
- Salary setup and payroll calculation
- Payrun processing
- Payslip generation
- Role-specific dashboards
- Monthly reports
- Admin settings for user roles and master data

### Out of Scope for MVP

- Biometric attendance integration
- Bank transfer integration
- Government filing integration
- Multi-company tenancy
- Advanced performance management
- Shift rostering
- Mobile application

## 5. User Roles and Permissions

### Admin

- Register and manage users
- Create, read, update, delete records across all modules
- Assign and change roles
- Access settings, reports, payroll, attendance, leave, and dashboards
- View all employee records and audit activity

### Employee

- Log in and manage own profile
- Mark attendance
- View own attendance logs
- Apply for leave/time-off
- View leave balance and request status
- View employee directory in read-only mode
- No access to payroll, salary data, system settings, or global reports

### HR Officer

- Create and update employee profiles
- View all employee attendance records
- Allocate leave balances and manage leave types
- View employee directory and personnel data
- No access to payroll values or system settings

### Payroll Officer

- View attendance needed for payroll processing
- Approve or reject leave requests
- Maintain salary-related information
- Run payroll and generate payslips/reports
- Access payroll, time-off, attendance, and reports
- No access to system settings
- No authority to create or modify non-salary employee master data

## 6. Permission Matrix

| Module / Action | Admin | Employee | HR Officer | Payroll Officer |
|---|---|---|---|---|
| Register/Login | Yes | Yes | Yes | Yes |
| Manage users | Yes | No | No | No |
| Assign roles | Yes | No | No | No |
| Edit own profile | Yes | Yes | Yes | Yes |
| Edit employee profile | Yes | No | Yes | Salary-only fields |
| View employee directory | Yes | Yes (read-only) | Yes | Yes |
| Mark attendance | Yes | Yes | Optional/manual correction | Optional/view |
| View own attendance | Yes | Yes | Yes | Yes |
| View all attendance | Yes | No | Yes | Yes |
| Apply leave | Yes | Yes | Optional on behalf | Optional on behalf |
| Approve/reject leave | Yes | No | Optional if allowed later | Yes |
| Allocate leave balances | Yes | No | Yes | No |
| Manage payroll setup | Yes | No | No | Yes |
| Run payrun | Yes | No | No | Yes |
| Generate payslip/report | Yes | No | No | Yes |
| Access analytics dashboard | Yes | Personal only | HR view | Payroll/ops view |
| Access settings | Yes | No | No | No |

## 7. Core Modules

### 7.1 Authentication and User Management

**Purpose:** Secure access and role-based entry into the system.

**Functions**

- User registration
- Login/logout
- Password reset
- Role assignment
- User activation/deactivation
- Profile update

**Key Fields**

- Full name
- Employee ID
- Email
- Phone
- Role
- Department
- Designation
- Date of joining
- Employment status
- Password hash
- Profile photo (optional)

**Rules**

- Email and employee ID must be unique
- Every user must have exactly one primary role
- Deactivated users cannot log in
- Employees can edit only allowed personal fields
- Only Admin can create and deactivate user accounts

### 7.2 Employee Profile and Directory

**Purpose:** Maintain employee master records.

**Functions**

- Add employee
- Update employee details
- View employee list
- Filter by department, role, status
- View employee detail page

**Profile Sections**

- Personal information
- Job information
- Contact information
- Emergency contact
- Leave balances
- Attendance summary
- Payroll summary (hidden from unauthorized roles)

### 7.3 Attendance Management

**Purpose:** Capture presence and working-day records used later in payroll.

**Functions**

- Daily check-in
- Daily check-out
- Automatic work-hours calculation
- View day-wise logs
- View monthly attendance summary
- Manual regularization/correction by Admin if needed

**Statuses**

- Present
- Absent
- Half Day
- On Leave
- Weekend
- Holiday
- Late

**Rules**

- Only one attendance record per employee per day
- Check-out cannot happen before check-in
- Approved leave converts day status to `On Leave`
- If no attendance and no approved leave on a working day, status becomes `Absent`
- Monthly attendance summary should show present days, absent days, leave days, and late marks

### 7.4 Leave and Time-Off Management

**Purpose:** Manage leave requests, balances, and approval outcomes.

**Functions**

- Configure leave types
- Allocate leave balances
- Employee leave application
- Leave approval or rejection
- Leave status tracking
- Leave history

**Suggested Leave Types**

- Casual Leave
- Sick Leave
- Earned Leave
- Unpaid Leave

**Request Data**

- Employee
- Leave type
- Start date
- End date
- Number of days
- Reason
- Attachment (optional)
- Status
- Approver comment

**Statuses**

- Pending
- Approved
- Rejected
- Cancelled

**Rules**

- Employees cannot request leave for invalid date ranges
- Leave balance must be checked before approval for paid leave types
- Unpaid leave can be approved even when paid balance is exhausted
- Approved leave must reduce balance
- Rejected leave must not affect balance
- Cancelled approved leave should restore balance if payroll is not locked

### 7.5 Payroll Management

**Purpose:** Calculate salary using employee salary structure, attendance, approved leave, and deductions.

**Functions**

- Define salary structure for each employee
- Create payrun for a month
- Fetch attendance and approved leave data for the period
- Compute earnings and deductions
- Review and adjust payroll
- Finalize payroll
- Generate payslips

**Payroll Inputs**

- Basic salary
- Allowances
- Bonuses
- Deductions
- Provident Fund contribution
- Professional tax
- Unpaid leave deduction
- Attendance-based deduction

**Suggested Salary Components**

- Basic
- House Rent Allowance
- Transport Allowance
- Special Allowance
- Bonus/Incentive
- Overtime (optional)
- PF deduction
- Professional tax
- Other deductions

**Calculation Logic**

1. Determine payable days in the month
2. Fetch attendance summary
3. Fetch approved paid and unpaid leave
4. Compute earned gross salary for payable days
5. Apply fixed deductions
6. Apply PF deduction
7. Apply professional tax
8. Calculate net pay

**Rules**

- Payroll is processed per payrun period
- Only finalized payroll generates official payslips
- Locked payruns cannot be edited without Admin override
- Attendance and approved leave must be frozen at payrun finalization

### 7.6 Payrun Management

**Purpose:** Manage monthly payroll cycles.

**Functions**

- Create payrun for selected month
- Draft payroll run
- Review exceptions
- Finalize payrun
- Re-open with admin authorization

**Payrun Statuses**

- Draft
- In Review
- Finalized
- Locked

**Rules**

- One payrun per company per month in MVP
- Same employee cannot have duplicate salary records for the same payrun
- Finalized payrun should store historical values even if profile data changes later

### 7.7 Payslip and Reports

**Purpose:** Produce official salary and operational outputs.

**Payslip Content**

- Employee details
- Pay period
- Earnings breakdown
- Deductions breakdown
- Gross pay
- Net pay
- Payment date

**Reports**

- Monthly payroll report
- Leave report
- Attendance report
- Employee master report

**Export Options**

- PDF for payslip
- CSV/Excel for reports

### 7.8 Dashboard and Analytics

**Purpose:** Provide snapshots for action and decision making.

**Admin Dashboard**

- Total employees
- Active vs inactive employees
- Attendance today
- Pending leave requests
- Payroll processed this month
- Department-wise employee count
- Monthly absence trend

**Employee Dashboard**

- Today’s attendance status
- Monthly attendance summary
- Leave balance
- Pending leave requests

**HR Dashboard**

- Employee count by department
- New joiners
- Leave balance summary
- Attendance exceptions

**Payroll Dashboard**

- Upcoming payrun
- Payroll cost summary
- Deduction summary
- Pending payroll actions

## 8. End-to-End Functional Workflows

### Workflow 1: User Onboarding

1. Admin creates employee account
2. Admin assigns role
3. HR Officer fills employee profile
4. Payroll Officer adds salary structure
5. Employee logs in and updates personal profile

### Workflow 2: Daily Attendance

1. Employee logs in
2. Employee marks check-in
3. Employee marks check-out at end of day
4. System calculates worked hours and status
5. Employee and authorized staff view logs

### Workflow 3: Leave Request

1. Employee selects leave type and dates
2. System validates balance and date range
3. Request is submitted as `Pending`
4. Payroll Officer reviews request
5. Request is approved or rejected
6. If approved, leave balance and attendance records are updated

### Workflow 4: Monthly Payroll Processing

1. Payroll Officer creates payrun for the month
2. System pulls attendance and approved leave data
3. System calculates gross pay, deductions, and net pay
4. Payroll Officer reviews exceptions and edits allowed values
5. Admin or Payroll Officer finalizes payroll
6. System generates payslips and payroll report

### Workflow 5: Reporting and Analytics

1. Admin/Payroll Officer chooses report type and month
2. System fetches module data
3. Report is displayed and exportable
4. Dashboard cards and charts update from current records

## 9. Business Rules

### Attendance Rules

- Working calendar must define weekends and holidays
- Missing attendance on a working day should be handled as absent unless approved leave exists
- Half-day attendance should affect payroll proportionally

### Leave Rules

- Paid leave consumes allocated balance
- Unpaid leave reduces payable salary
- Overlapping leave requests are not allowed
- Leave cannot be approved for deactivated employees

### Payroll Rules

- Payroll is based on attendance and approved leave for the pay period
- PF contribution is commonly 12% of basic salary
- Professional tax is a fixed or configurable monthly deduction
- Unpaid leave reduces earnings based on per-day salary
- Payroll history must remain immutable after finalization unless re-opened by Admin

### Security Rules

- Role-based route and action protection is mandatory
- Users must see only data allowed by role
- Salary details must be protected from Employee and HR Officer access
- Important actions should be audit-logged

## 10. Suggested Data Model

### Main Entities

- User
- Role
- EmployeeProfile
- Department
- AttendanceRecord
- LeaveType
- LeaveBalance
- LeaveRequest
- SalaryStructure
- Payrun
- PayrollRecord
- Payslip
- Holiday
- AuditLog

### Key Relationships

- One `User` belongs to one `Role`
- One `User` has one `EmployeeProfile`
- One `EmployeeProfile` has many `AttendanceRecord`s
- One `EmployeeProfile` has many `LeaveRequest`s
- One `EmployeeProfile` has many `LeaveBalance`s by leave type
- One `EmployeeProfile` has one active `SalaryStructure`
- One `Payrun` has many `PayrollRecord`s
- One `PayrollRecord` generates one `Payslip`

## 11. Suggested Screens

- Login
- Register
- Forgot password
- Role-based dashboard
- Employee directory
- Employee profile detail
- Attendance mark screen
- Attendance monthly log screen
- Leave apply screen
- Leave approval queue
- Leave balance screen
- Payroll setup screen
- Payrun list
- Payrun detail/review screen
- Payslip viewer
- Reports screen
- Settings and role management

## 12. Non-Functional Requirements

- Clean and simple UI
- Responsive layout for desktop and mobile web
- Secure password storage
- Input validation on all forms
- Audit trail for critical actions
- Fast filtering and reporting for moderate employee counts
- Scalable module design for future enhancements
- Backup-friendly database structure

## 13. MVP Deliverables

### Must-Have

- Authentication with role-based access
- Employee profile CRUD
- Attendance marking and logs
- Leave request and approval flow
- Basic payroll calculation
- Monthly payrun generation
- Payslip generation
- Dashboard summaries
- Git repository with meaningful commits

### Good-to-Have

- Export to PDF/CSV
- Holiday calendar
- Attendance corrections
- Late mark tracking
- Notification system
- Audit log viewer

## 14. Acceptance Criteria

### Authentication

- Users can register and log in successfully
- Users are redirected to role-specific dashboards
- Unauthorized module access is blocked

### Employee Management

- Admin and HR can create and edit employee records
- Employees can edit only allowed profile fields

### Attendance

- Employee can mark attendance once per day
- Monthly logs show correct totals

### Leave

- Employees can apply for leave
- Payroll Officer can approve/reject requests
- Balance updates correctly after approval

### Payroll

- Payroll uses attendance and approved leave data
- System generates correct gross pay, deductions, and net pay
- Payslip is generated after payrun finalization

### Dashboard

- Dashboard shows role-appropriate metrics
- Attendance, leave, and payroll summaries update with system data

## 15. Suggested Implementation Plan

### Phase 1: Foundation

- Finalize requirements
- Define roles and permissions
- Set up database schema
- Build authentication and route protection

### Phase 2: Employee and Attendance

- Build employee profile module
- Build attendance mark and log features
- Add monthly attendance summary

### Phase 3: Leave Management

- Build leave types and balances
- Build leave application and approval workflow
- Connect approved leave with attendance

### Phase 4: Payroll Core

- Build salary structure management
- Build payrun engine
- Add PF, professional tax, and unpaid leave deductions
- Generate payroll records and payslips

### Phase 5: Dashboards and Reports

- Build admin, employee, HR, and payroll dashboards
- Add charts and monthly reports
- Add export options

### Phase 6: Stabilization

- Add validations and audit logs
- Test role permissions
- Test payroll edge cases
- Improve UI/UX and responsiveness

## 16. Testing Plan

### Functional Testing

- Role access validation
- Attendance submission cases
- Leave approval/rejection cases
- Payroll calculations across different attendance scenarios
- Payslip generation

### Edge Cases

- Leave across month boundary
- Employee with zero paid leave balance
- Half-day plus approved leave
- Finalized payrun reopened by Admin
- Deactivated user with old payroll history

### Sample Payroll Test Scenarios

- Full attendance month
- Month with paid leave only
- Month with unpaid leave
- Month with absences and late marks
- Employee joined in the middle of the month

## 17. Risks and Controls

### Key Risks

- Incorrect payroll logic
- Weak role restriction causing data exposure
- Inconsistent attendance and leave synchronization
- Missing historical payroll snapshots

### Controls

- Freeze records at payrun finalization
- Add audit logs for payroll and approval actions
- Use strict backend authorization checks
- Validate salary formulas with test cases

## 18. Recommended Tech Direction

This is optional for the problem statement, but a practical build could use:

- Frontend: React or Next.js
- Backend: Node.js/Express or NestJS
- Database: PostgreSQL or MySQL
- Auth: JWT/session-based auth with hashed passwords
- Reporting: PDF generation and CSV export
- Charts: Lightweight chart library for dashboard metrics

## 19. Final Functional Definition

EmPay should be delivered as a role-driven HRMS where:

- Admin controls the platform
- Employees self-manage attendance and time-off
- HR maintains employee and leave master data
- Payroll Officer converts attendance and approved leave into salary outputs
- Dashboards present the operational picture to each role

If built to this plan, the system will satisfy the problem statement and also feel complete from a real-world business workflow perspective rather than just as a set of disconnected screens.
