import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "../styles.css";

function createInitialState() {
  const today = new Date().toISOString().slice(0, 10);
  const month = today.slice(0, 7);
  return {
    screen: "public",
    authMode: "login",
    status: { message: "", type: "info" },
    profileMenuOpen: false,
    me: null,
    role: null,
    settings: { companyName: "EmPay" },
    permissions: {},
    view: "dashboard",
    dashboard: null,
    employees: [],
    leaveTypes: [],
    leaveBalances: [],
    leaves: [],
    attendance: null,
    salaryStructures: [],
    payruns: [],
    payslips: [],
    report: null,
    auditLogs: [],
    selectedUserId: null,
    quickAttendance: null,
    currentMonth: month,
    currentDate: today,
    attendanceFilter: { month, day: "", employeeId: "" },
    leaveFilter: { month, status: "", fromDate: "", toDate: "", employeeId: "" },
    payrollFilter: { month, employeeId: "", payrunStatus: "" },
    reportType: "attendance",
  };
}

const viewConfig = {
  dashboard: { label: "Dashboard", roles: ["Admin", "Employee", "HR Officer", "Payroll Officer"] },
  manageUsers: { label: "Manage Users", roles: ["Admin"] },
  people: { label: "People Directory", roles: ["HR Officer", "Payroll Officer"] },
  attendance: { label: "Attendance", roles: ["Admin", "Employee", "HR Officer", "Payroll Officer"] },
  leave: { label: "Leave", roles: ["Admin", "Employee", "HR Officer", "Payroll Officer"] },
  payroll: { label: "Payroll", roles: ["Admin", "Employee", "Payroll Officer"] },
  reports: { label: "Reports", roles: ["Admin", "HR Officer", "Payroll Officer"] },
  profile: { label: "My Profile", roles: ["Admin", "Employee", "HR Officer", "Payroll Officer"] },
  audit: { label: "Audit Log", roles: ["Admin"] },
};

function query(params) {
  const search = new URLSearchParams();
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, value);
    }
  });
  return search.toString();
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    throw new Error(payload?.error || "Request failed");
  }
  return payload;
}

function formatCurrency(value) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

function formatDate(value) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatTime(value) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleTimeString("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function tagClass(value) {
  const normalized = String(value || "").toLowerCase();
  if (["approved", "active", "present", "locked", "finalized"].includes(normalized)) {
    return "success";
  }
  if (["pending", "draft", "in progress", "late", "half day"].includes(normalized)) {
    return "warning";
  }
  if (["rejected", "cancelled", "absent", "inactive"].includes(normalized)) {
    return "danger";
  }
  return "info";
}

function initialsFor(name) {
  return String(name || "EmPay")
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("");
}

function formatReportColumnLabel(column) {
  const normalized = String(column || "")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .trim();
  return normalized.replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatReportCell(column, value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (/date/i.test(column) && /^\d{4}-\d{2}-\d{2}/.test(String(value))) {
    return formatDate(value);
  }
  if (/(gross|deduction|net|wage|amount|tax|salary|pay)$/i.test(column) && !Number.isNaN(Number(value))) {
    return formatCurrency(value);
  }
  return String(value);
}

function toCsv(rows) {
  if (!rows.length) {
    return "";
  }
  const headers = Object.keys(rows[0]);
  return [
    headers.join(","),
    ...rows.map((row) =>
      headers.map((header) => `"${String(row[header] ?? "").replaceAll('"', '""')}"`).join(",")
    ),
  ].join("\n");
}

function downloadCsv(filename, rows) {
  const blob = new Blob([toCsv(rows)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function triggerPayslipDownload(employeeId, month) {
  window.open(`/api/payslips/download?${query({ employeeId, month })}`, "_blank");
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function Tag({ value }) {
  return <span className={`tag ${tagClass(value)}`}>{value ?? "-"}</span>;
}

function Metrics({ cards }) {
  return (
    <section className="metrics-grid">
      {cards.map((card) => (
        <article className="metric-card" key={card.label}>
          <span className="eyebrow">{card.label}</span>
          <strong>{card.value}</strong>
        </article>
      ))}
    </section>
  );
}

function SalaryCard({ salaryInfo, title }) {
  if (!salaryInfo) {
    return (
      <section className="salary-card">
        <h3>{title}</h3>
        <div className="empty-state">No salary structure is configured yet.</div>
      </section>
    );
  }

  const items = [
    ["Basic Salary", salaryInfo.breakdown.basicSalary],
    ["House Rent Allowance", salaryInfo.breakdown.houseRentAllowance],
    ["Standard Allowance", salaryInfo.breakdown.standardAllowance],
    ["Performance Bonus", salaryInfo.breakdown.performanceBonus],
    ["Leave Travel Allowance", salaryInfo.breakdown.leaveTravelAllowance],
    ["Fixed Allowance", salaryInfo.breakdown.fixedAllowance],
  ];

  return (
    <section className="salary-card">
      <div className="salary-header">
        <div>
          <span className="eyebrow">Compensation</span>
          <h3>{title}</h3>
        </div>
        <Tag value="Salary Info" />
      </div>
      <div className="salary-grid">
        <div className="stack">
          <div className="salary-summary-grid">
            <div className="stat-block">
              <span className="eyebrow">Month Wage</span>
              <strong>{formatCurrency(salaryInfo.monthWage)}</strong>
              <div className="metric-subtext">per month</div>
            </div>
            <div className="stat-block">
              <span className="eyebrow">Yearly Wage</span>
              <strong>{formatCurrency(salaryInfo.yearWage)}</strong>
              <div className="metric-subtext">per year</div>
            </div>
            <div className="stat-block">
              <span className="eyebrow">Working Days / Week</span>
              <strong>{salaryInfo.workingDaysPerWeek}</strong>
            </div>
            <div className="stat-block">
              <span className="eyebrow">Break Time</span>
              <strong>{salaryInfo.breakHours} hrs</strong>
            </div>
          </div>
          <div>
            <h4 className="salary-section-title">Salary Components</h4>
            {items.map(([label, item]) => (
              <div className="salary-line" key={label}>
                <div>
                  <strong>{label}</strong>
                  <div className="metric-subtext">{item.note}</div>
                </div>
                <div>
                  {formatCurrency(item.amount)} / month <strong>{item.percentage}%</strong>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="stack">
          <div>
            <h4 className="salary-section-title">Provident Fund (PF) Contribution</h4>
            <div className="salary-line">
              <div>
                <strong>Employee</strong>
                <div className="metric-subtext">PF is calculated based on the basic salary.</div>
              </div>
              <div>
                {formatCurrency(salaryInfo.providentFund.employeeAmount)} / month{" "}
                <strong>{salaryInfo.providentFund.employeePercentage}%</strong>
              </div>
            </div>
            <div className="salary-line">
              <div>
                <strong>Employer</strong>
                <div className="metric-subtext">PF is calculated based on the basic salary.</div>
              </div>
              <div>
                {formatCurrency(salaryInfo.providentFund.employerAmount)} / month{" "}
                <strong>{salaryInfo.providentFund.employerPercentage}%</strong>
              </div>
            </div>
          </div>
          <div>
            <h4 className="salary-section-title">Tax Deductions</h4>
            <div className="salary-line">
              <div>
                <strong>Professional Tax</strong>
                <div className="metric-subtext">Professional tax deducted from the gross salary.</div>
              </div>
              <div>{formatCurrency(salaryInfo.tax.professionalTax)} / month</div>
            </div>
            <div className="salary-line">
              <div>
                <strong>Other Deduction</strong>
                <div className="metric-subtext">Any additional fixed deduction maintained in payroll.</div>
              </div>
              <div>{formatCurrency(salaryInfo.tax.otherDeduction)} / month</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function PublicScreen({ onMode }) {
  return (
    <section className="public-shell">
      <header className="landing-header">
        <div className="brand-lockup">
          <span className="brand-mark">EmPay</span>
          <span className="brand-copy">Smart Human Resource Management</span>
        </div>
        <div className="header-actions">
          <button className="button ghost" onClick={() => onMode("login")}>
            Login
          </button>
          <button className="button primary" onClick={() => onMode("signup")}>
            Start Free Setup
          </button>
        </div>
      </header>
      <main className="landing-main">
        <section className="hero-copy">
          <span className="eyebrow">Built for modern operations</span>
          <h1>Run people, attendance, leave, and payroll from one calm workspace.</h1>
          <p>
            EmPay brings together employee management, attendance visibility, filtered leave workflows,
            and payroll history in one clean system designed for startups, institutions, and growing teams.
          </p>
          <div className="hero-actions">
            <button className="button primary" onClick={() => onMode("signup")}>
              Create Workspace
            </button>
            <button className="button ghost" onClick={() => onMode("login")}>
              Login to Dashboard
            </button>
          </div>
          <div className="hero-points">
            <div className="hero-point">Role-based HRMS</div>
            <div className="hero-point">Manual attendance with check-in and check-out time</div>
            <div className="hero-point">Payslip generation and downloads</div>
          </div>
        </section>
        <section className="hero-preview card">
          <div className="hero-glow"></div>
          <div className="preview-top">
            <div>
              <span className="eyebrow">Operations Snapshot</span>
              <h2>Everything the team needs, nothing noisy.</h2>
            </div>
            <Tag value="Odoo-style flow" />
          </div>
          <div className="floating-ribbon ribbon-one">Attendance</div>
          <div className="floating-ribbon ribbon-two">Payroll</div>
          <div className="floating-ribbon ribbon-three">Reports</div>
          <div className="preview-metrics">
            <article>
              <span>Total People</span>
              <strong>128</strong>
            </article>
            <article>
              <span>Pending Leave</span>
              <strong>09</strong>
            </article>
            <article>
              <span>Payroll Ready</span>
              <strong>96%</strong>
            </article>
          </div>
          <div className="preview-columns">
            <div className="preview-block">
              <h3>People Operations</h3>
              <p>Manage employees, HR officers, and payroll officers with clear responsibilities.</p>
            </div>
            <div className="preview-block">
              <h3>Attendance Ownership</h3>
              <p>Every user marks their own attendance with date and time. Managers only view logs.</p>
            </div>
            <div className="preview-block">
              <h3>Payroll Control</h3>
              <p>Generate payruns, maintain salary structures, track history, and download payslips.</p>
            </div>
          </div>
        </section>
      </main>
    </section>
  );
}

function AuthScreen({ mode, status, onBack, onModeChange, onLogin, onSignup }) {
  return (
    <section className="auth-shell">
      <div className="auth-wrapper card">
        <div className="auth-intro">
          <button className="back-link" onClick={onBack}>
            Back to landing
          </button>
          <span className="eyebrow">EmPay Access</span>
          <h2>{mode === "login" ? "Login" : "Create your workspace"}</h2>
          <p>
            {mode === "login"
              ? "Sign in to your workspace and continue from where your team left off."
              : "Create an admin workspace, set your company name, and start onboarding your team."}
          </p>
          <div className={`status-banner ${status.message ? status.type : ""}`}>{status.message}</div>
        </div>
        {mode === "login" ? (
          <form
            className="form-grid"
            onSubmit={(event) => {
              event.preventDefault();
              onLogin(Object.fromEntries(new FormData(event.currentTarget).entries()));
            }}
          >
            <label>
              <span>Email</span>
              <input type="email" name="email" defaultValue="admin@empay.local" required />
            </label>
            <label>
              <span>Password</span>
              <input type="password" name="password" defaultValue="Admin@123" required />
            </label>
            <button type="submit" className="button primary">
              Login
            </button>
            <p className="auth-switch">
              Don&apos;t have an account?{" "}
              <button type="button" className="inline-link" onClick={() => onModeChange("signup")}>
                Sign up
              </button>
            </p>
          </form>
        ) : (
          <form
            className="form-grid"
            onSubmit={(event) => {
              event.preventDefault();
              onSignup(Object.fromEntries(new FormData(event.currentTarget).entries()));
            }}
          >
            <label>
              <span>Company Name</span>
              <input name="companyName" required />
            </label>
            <label>
              <span>Name</span>
              <input name="fullName" required />
            </label>
            <div className="split-grid">
              <label>
                <span>Email</span>
                <input type="email" name="email" required />
              </label>
              <label>
                <span>Phone</span>
                <input name="phone" required />
              </label>
            </div>
            <div className="split-grid">
              <label>
                <span>Password</span>
                <input type="password" name="password" required />
              </label>
              <label>
                <span>Confirm Password</span>
                <input type="password" name="confirmPassword" required />
              </label>
            </div>
            <button type="submit" className="button primary">
              Create Admin Workspace
            </button>
            <p className="auth-switch">
              Already have an account?{" "}
              <button type="button" className="inline-link" onClick={() => onModeChange("login")}>
                Login
              </button>
            </p>
          </form>
        )}
      </div>
    </section>
  );
}

function QuickAttendanceCard({ record, currentDate, onSubmit }) {
  const checkedOut = Boolean(record?.checkOut);
  const isActive = Boolean(record?.checkIn);
  return (
    <section className="quick-attendance-card">
      <div className="quick-attendance-head">
        <div>
          <span className="eyebrow">Quick Attendance</span>
          <div className="metric-subtext">
            {checkedOut ? "Checked out" : isActive ? "Checked in" : "Not checked in"}
          </div>
        </div>
        <span className={`status-dot ${isActive ? "active" : ""}`}></span>
      </div>
      <form
        className="form-grid"
        onSubmit={(event) => {
          event.preventDefault();
          const data = Object.fromEntries(new FormData(event.currentTarget).entries());
          onSubmit({ ...data, action: event.nativeEvent.submitter?.value });
        }}
      >
        <label>
          <span>Date</span>
          <input type="date" name="date" defaultValue={currentDate} required />
        </label>
        <label>
          <span>Time</span>
          <input type="time" name="time" defaultValue={checkedOut ? "18:00" : "09:00"} required />
        </label>
        <div className="metric-subtext">
          {record?.checkIn
            ? `Since ${formatTime(record.checkIn)}${record.checkOut ? `, checked out at ${formatTime(record.checkOut)}` : ""}`
            : "Use the button below to mark your attendance."}
        </div>
        <div className="inline-actions">
          {!record?.checkIn && (
            <button type="submit" className="button primary small" value="checkin">
              Check In
            </button>
          )}
          {record?.checkIn && !record?.checkOut && (
            <button type="submit" className="button secondary small" value="checkout">
              Check Out
            </button>
          )}
        </div>
      </form>
    </section>
  );
}

function DashboardView({ dashboard, role, settings }) {
  const pendingLeaves = dashboard.pendingLeaves || dashboard.recentLeaves || [];
  const sideContent = dashboard.departmentStats
    ? Object.entries(dashboard.departmentStats).map(([key, value]) => (
        <div className="stat-block" key={key}>
          <span className="eyebrow">{key}</span>
          <strong>{value}</strong>
        </div>
      ))
    : (dashboard.leaveBalances || []).map((balance) => (
        <div className="list-item" key={balance.id}>
          <strong>{balance.leaveTypeName}</strong>
          <div className="metric-subtext">{balance.balance} days remaining</div>
        </div>
      ));

  return (
    <>
      <Metrics cards={dashboard.cards} />
      <section className="panel-grid">
        <article className="panel">
          <div className="panel-actions">
            <div>
              <span className="eyebrow">Company</span>
              <h3>{settings.companyName}</h3>
            </div>
            <Tag value={role} />
          </div>
          <div className="stack">
            {dashboard.attendance ? (
              <div className="stat-block">
                <span className="eyebrow">Attendance Snapshot</span>
                <strong>{dashboard.attendance.payableDays} payable days</strong>
                <div className="metric-subtext">
                  {dashboard.attendance.presentDays} present, {dashboard.attendance.absentDays} absent,{" "}
                  {dashboard.attendance.extraHours} extra hours
                </div>
              </div>
            ) : dashboard.latestPayrun ? (
              <div className="stat-block">
                <span className="eyebrow">Latest Payrun</span>
                <strong>{dashboard.latestPayrun.month}</strong>
                <div className="metric-subtext">
                  {dashboard.latestPayrun.records.length} records, {dashboard.latestPayrun.status}
                </div>
              </div>
            ) : (
              <div className="empty-state">No latest payrun is available yet.</div>
            )}
            <div className="panel-grid">{sideContent}</div>
          </div>
        </article>
        <article className="panel">
          <div className="panel-actions">
            <div>
              <span className="eyebrow">Workflow Queue</span>
              <h3>{role === "Employee" ? "Recent Leave Requests" : "Pending Leave Requests"}</h3>
            </div>
          </div>
          <div className="list">
            {pendingLeaves.length ? (
              pendingLeaves.map((item, index) => (
                <div className="list-item" key={`${item.id || item.startDate}-${index}`}>
                  <strong>{item.employeeName || item.leaveTypeName || item.startDate}</strong>
                  <div className="metric-subtext">
                    {item.startDate || item.leaveTypeName || ""}
                    {item.endDate ? ` to ${item.endDate}` : ""}
                    {item.status ? `, ${item.status}` : ""}
                  </div>
                </div>
              ))
            ) : (
              <div className="empty-state">Nothing is waiting right now.</div>
            )}
          </div>
        </article>
      </section>
    </>
  );
}

function DirectoryTable({ employees, onSelect, showAction = false }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>User</th>
            <th>Role</th>
            <th>Check In</th>
            <th>Check Out</th>
            <th>Working Hours</th>
            <th>Extra Hours</th>
            <th>Status</th>
            {showAction && <th>Action</th>}
          </tr>
        </thead>
        <tbody>
          {employees.map((employee) => (
            <tr key={employee.id}>
              <td>
                <strong>{employee.fullName}</strong>
                <br />
                <span className="muted">
                  {employee.employeeId} | {employee.email}
                </span>
              </td>
              <td>{employee.role}</td>
              <td>{formatTime(employee.attendanceSnapshot?.checkIn)}</td>
              <td>{formatTime(employee.attendanceSnapshot?.checkOut)}</td>
              <td>{employee.attendanceSnapshot?.workedHours || 0}</td>
              <td>{employee.attendanceSnapshot?.extraHours || 0}</td>
              <td>
                <Tag value={employee.attendanceSnapshot?.status || "No Record"} />
              </td>
              {showAction && (
                <td>
                  <button className="button ghost small" onClick={() => onSelect(employee.id)}>
                    View
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function App() {
  const [state, setState] = useState(createInitialState);

  const availableViews = useMemo(
    () =>
      Object.entries(viewConfig)
        .filter(([, config]) => state.role && config.roles.includes(state.role))
        .map(([key, config]) => ({ key, ...config })),
    [state.role]
  );

  const visibleEmployeeId = state.role === "Employee" ? state.me?.id : state.selectedUserId || state.me?.id;
  const selectedUser = state.employees.find((employee) => employee.id === visibleEmployeeId) || state.employees[0];
  const currentSalaryStructure = state.salaryStructures[0] || null;

  function setStatus(message = "", type = "info") {
    setState((prev) => ({ ...prev, status: { message, type } }));
  }

  async function bootstrap() {
    try {
      const auth = await api("/api/auth/me");
      setState((prev) => ({
        ...prev,
        screen: "app",
        me: auth.user,
        role: auth.role,
        settings: auth.settings || prev.settings,
        permissions: auth.permissions || {},
        selectedUserId: auth.user.id,
        attendanceFilter: { ...prev.attendanceFilter, employeeId: auth.user.id },
        leaveFilter: { ...prev.leaveFilter, employeeId: auth.user.id },
        payrollFilter: { ...prev.payrollFilter, employeeId: auth.user.id },
      }));
      await loadView("dashboard", {
        me: auth.user,
        role: auth.role,
        permissions: auth.permissions || {},
        settings: auth.settings || state.settings,
        selectedUserId: auth.user.id,
      });
    } catch {
      setState((prev) => ({ ...prev, screen: "public" }));
    }
  }

  async function loadEmployees(includeAdmins = false) {
    const payload = await api(includeAdmins ? "/api/employees?includeAdmins=true" : "/api/employees");
    setState((prev) => ({ ...prev, employees: payload.employees }));
    return payload.employees;
  }

  async function loadQuickAttendance(ctx = state) {
    const role = ctx.role ?? state.role;
    const me = ctx.me ?? state.me;
    if (role !== "Employee" || !me) {
      setState((prev) => ({ ...prev, quickAttendance: null }));
      return null;
    }
    const payload = await api(
      `/api/attendance?${query({
        employeeId: me.id,
        month: ctx.currentMonth || state.currentMonth,
        day: ctx.currentDate || state.currentDate,
      })}`
    );
    const record = payload.records[0] || null;
    setState((prev) => ({ ...prev, quickAttendance: record }));
    return record;
  }

  async function loadDashboard(ctx = state) {
    const dashboard = await api(`/api/dashboard?month=${ctx.currentMonth || state.currentMonth}`);
    setState((prev) => ({ ...prev, dashboard }));
  }

  async function loadAttendance(filter = state.attendanceFilter, ctx = state) {
    const role = ctx.role ?? state.role;
    if (ctx.permissions?.canViewAttendanceDirectory || role === "Employee") {
      await loadEmployees(role === "Admin");
    }
    const attendance = await api(`/api/attendance?${query(filter)}`);
    setState((prev) => ({ ...prev, attendance, attendanceFilter: filter }));
  }

  async function loadLeaveData(filter = state.leaveFilter, ctx = state) {
    await loadEmployees((ctx.role ?? state.role) === "Admin");
    const leaveTypes = (await api("/api/leave-types")).leaveTypes;
    const leaves = (await api(`/api/leaves?${query(filter)}`)).leaveRequests;
    const employeeId = (ctx.role ?? state.role) === "Employee" ? (ctx.me ?? state.me).id : filter.employeeId || (ctx.me ?? state.me).id;
    const leaveBalances = (await api(`/api/leave-balances?employeeId=${employeeId}`)).balances;
    setState((prev) => ({ ...prev, leaveTypes, leaves, leaveBalances, leaveFilter: filter }));
  }

  async function loadPayrollData(filter = state.payrollFilter, ctx = state) {
    const role = ctx.role ?? state.role;
    const me = ctx.me ?? state.me;
    await loadEmployees(role === "Admin");
    const employeeId = role === "Employee" ? me.id : filter.employeeId;
    const salaryStructures = (
      await api(employeeId ? `/api/payroll/structures?employeeId=${employeeId}` : "/api/payroll/structures")
    ).structures;
    const payruns =
      role !== "Employee"
        ? (await api(`/api/payruns?${query({ month: filter.month, status: filter.payrunStatus })}`)).payruns
        : [];
    const payslips = (
      await api(
        `/api/payslips?${query({
          month: filter.month,
          employeeId: role === "Employee" ? me.id : filter.employeeId,
        })}`
      )
    ).payslips;
    setState((prev) => ({ ...prev, salaryStructures, payruns, payslips, payrollFilter: filter }));
  }

  async function loadReports(type = state.reportType, month = state.currentMonth) {
    const report = await api(`/api/reports?type=${type}&month=${month}`);
    setState((prev) => ({ ...prev, report, reportType: type, currentMonth: month }));
  }

  async function loadAudit() {
    const auditLogs = (await api("/api/audit-logs")).logs;
    setState((prev) => ({ ...prev, auditLogs }));
  }

  async function loadProfileData(ctx = state) {
    const me = ctx.me ?? state.me;
    const salaryStructures = (await api(`/api/payroll/structures?employeeId=${me.id}`)).structures;
    let payslips = [];
    try {
      payslips = (await api(`/api/payslips?employeeId=${me.id}&month=${ctx.currentMonth || state.currentMonth}`)).payslips;
    } catch {
      payslips = [];
    }
    setState((prev) => ({ ...prev, salaryStructures, payslips }));
  }

  async function loadView(view, ctx = state) {
    setState((prev) => ({ ...prev, view, profileMenuOpen: false }));
    if ((ctx.role ?? state.role) === "Employee") {
      await loadQuickAttendance(ctx);
    } else {
      setState((prev) => ({ ...prev, quickAttendance: null }));
    }
    if (view === "dashboard") return loadDashboard(ctx);
    if (view === "manageUsers") {
      await loadEmployees(true);
      return;
    }
    if (view === "people") {
      await loadEmployees(false);
      return;
    }
    if (view === "attendance") return loadAttendance(ctx.attendanceFilter || state.attendanceFilter, ctx);
    if (view === "leave") return loadLeaveData(ctx.leaveFilter || state.leaveFilter, ctx);
    if (view === "payroll") return loadPayrollData(ctx.payrollFilter || state.payrollFilter, ctx);
    if (view === "reports") return loadReports(ctx.reportType || state.reportType, ctx.currentMonth || state.currentMonth);
    if (view === "profile") return loadProfileData(ctx);
    if (view === "audit") return loadAudit();
  }

  useEffect(() => {
    bootstrap();
  }, []);

  useEffect(() => {
    function handleClick(event) {
      if (!event.target.closest(".profile-menu")) {
        setState((prev) => ({ ...prev, profileMenuOpen: false }));
      }
    }
    window.addEventListener("click", handleClick);
    return () => window.removeEventListener("click", handleClick);
  }, []);

  async function handleLogin(values) {
    try {
      await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify(values),
      });
      setStatus("Login successful.", "success");
      await bootstrap();
    } catch (error) {
      setStatus(error.message, "error");
    }
  }

  async function handleSignup(values) {
    try {
      await api("/api/auth/signup", {
        method: "POST",
        body: JSON.stringify(values),
      });
      setStatus("Workspace created successfully.", "success");
      await bootstrap();
    } catch (error) {
      setStatus(error.message, "error");
    }
  }

  async function handleLogout() {
    await api("/api/auth/logout", { method: "POST" });
    setState(createInitialState());
  }

  async function handleQuickAttendance(values) {
    try {
      await api("/api/attendance/mark", {
        method: "POST",
        body: JSON.stringify(values),
      });
      setStatus(`Attendance ${values.action} recorded.`, "success");
      await loadQuickAttendance();
      if (state.view === "attendance" || state.view === "dashboard") {
        await loadView(state.view);
      }
    } catch (error) {
      setStatus(error.message, "error");
    }
  }

  async function handleCreateUser(values) {
    try {
      await api("/api/employees", {
        method: "POST",
        body: JSON.stringify(values),
      });
      setStatus("New user created.", "success");
      await loadView("manageUsers");
    } catch (error) {
      setStatus(error.message, "error");
    }
  }

  async function handleUpdateUser(values) {
    try {
      await api(`/api/employees/${values.id}`, {
        method: "PUT",
        body: JSON.stringify({ ...values, active: values.active === "true" }),
      });
      setStatus("User updated successfully.", "success");
      await loadView("manageUsers");
    } catch (error) {
      setStatus(error.message, "error");
    }
  }

  async function handleAttendanceMark(values) {
    try {
      await api("/api/attendance/mark", {
        method: "POST",
        body: JSON.stringify(values),
      });
      setStatus(`Attendance ${values.action} recorded.`, "success");
      await loadView("attendance");
    } catch (error) {
      setStatus(error.message, "error");
    }
  }

  async function handleLeaveAction(values) {
    try {
      await api(`/api/leaves/${values.id}`, {
        method: "PATCH",
        body: JSON.stringify({ action: values.action }),
      });
      setStatus(`Leave request ${values.action}d successfully.`, "success");
      await loadView("leave");
    } catch (error) {
      setStatus(error.message, "error");
    }
  }

  async function handleProfilePhotoChange(file) {
    try {
      const profilePhoto = await readFileAsDataUrl(file);
      setState((prev) => ({
        ...prev,
        me: { ...prev.me, profilePhoto },
      }));
      setStatus("Profile photo ready to save.", "info");
    } catch {
      setStatus("Could not read the selected image.", "error");
    }
  }

  async function handleProfileSave(values) {
    try {
      await api(`/api/employees/${state.me.id}`, {
        method: "PUT",
        body: JSON.stringify(values),
      });
      setStatus("Profile updated.", "success");
      await bootstrap();
      await loadView("profile");
    } catch (error) {
      setStatus(error.message, "error");
    }
  }

  if (state.screen === "public") {
    return (
      <>
        <div className="ambient ambient-one"></div>
        <div className="ambient ambient-two"></div>
        <PublicScreen
          onMode={(mode) => setState((prev) => ({ ...prev, screen: "auth", authMode: mode }))}
        />
      </>
    );
  }

  if (state.screen === "auth") {
    return (
      <>
        <div className="ambient ambient-one"></div>
        <div className="ambient ambient-two"></div>
        <AuthScreen
          mode={state.authMode}
          status={state.status}
          onBack={() => setState((prev) => ({ ...prev, screen: "public" }))}
          onModeChange={(authMode) => setState((prev) => ({ ...prev, authMode }))}
          onLogin={handleLogin}
          onSignup={handleSignup}
        />
      </>
    );
  }

  return (
    <>
      <div className="ambient ambient-one"></div>
      <div className="ambient ambient-two"></div>
      <section className="app-shell">
        <aside className="app-sidebar card">
          <div className="sidebar-top">
            <span className="brand-mark">EmPay</span>
            <p className="muted">{state.settings.companyName}</p>
          </div>
          <nav className="nav">
            {availableViews.map((item) => (
              <button
                key={item.key}
                className={state.view === item.key ? "active" : ""}
                onClick={() => loadView(item.key)}
              >
                {item.label}
              </button>
            ))}
          </nav>
          <div className="sidebar-utility">
            {state.role === "Employee" && (
              <QuickAttendanceCard
                record={state.quickAttendance}
                currentDate={state.currentDate}
                onSubmit={handleQuickAttendance}
              />
            )}
          </div>
        </aside>
        <main className="app-main">
          <header className="app-header">
            <div>
              <span className="eyebrow">Workspace</span>
              <h1>{viewConfig[state.view]?.label || "Dashboard"}</h1>
            </div>
            <div className="header-right">
              <div className={`status-banner ${state.status.message ? state.status.type : ""}`}>
                {state.status.message}
              </div>
              <div className="profile-menu">
                <button
                  className="profile-button"
                  onClick={(event) => {
                    event.stopPropagation();
                    setState((prev) => ({ ...prev, profileMenuOpen: !prev.profileMenuOpen }));
                  }}
                >
                  <span>
                    {state.me?.profilePhoto ? (
                      <img src={state.me.profilePhoto} alt={state.me.fullName} />
                    ) : (
                      initialsFor(state.me?.fullName)
                    )}
                  </span>
                  <strong>{state.me?.fullName}</strong>
                </button>
                {!state.profileMenuOpen ? null : (
                  <div className="profile-dropdown">
                    <button className="dropdown-item" onClick={() => loadView("profile")}>
                      My Profile
                    </button>
                    <button className="dropdown-item danger" onClick={handleLogout}>
                      Logout
                    </button>
                  </div>
                )}
              </div>
            </div>
          </header>
          <section className="view-container">
            {state.view === "dashboard" && state.dashboard && (
              <DashboardView dashboard={state.dashboard} role={state.role} settings={state.settings} />
            )}

            {state.view === "manageUsers" && (
              <>
                <section className="table-card">
                  <div className="panel-actions">
                    <div>
                      <span className="eyebrow">Admin Controls</span>
                      <h3>Manage Users</h3>
                      <div className="table-note">
                        Admin can manage Employee, HR Officer, and Payroll Officer accounts only.
                      </div>
                    </div>
                  </div>
                  <DirectoryTable employees={state.employees} onSelect={(id) => setState((prev) => ({ ...prev, selectedUserId: id }))} showAction />
                </section>
                <section className="panel-grid">
                  <article className="panel">
                    <div className="panel-actions">
                      <div>
                        <span className="eyebrow">User Detail</span>
                        <h3>{selectedUser?.fullName || "Select a user"}</h3>
                      </div>
                    </div>
                    {selectedUser ? (
                      <form
                        key={selectedUser.id}
                        className="form-grid two-col"
                        onSubmit={(event) => {
                          event.preventDefault();
                          handleUpdateUser(Object.fromEntries(new FormData(event.currentTarget).entries()));
                        }}
                      >
                        <input type="hidden" name="id" value={selectedUser.id} />
                        <label><span>Full Name</span><input name="fullName" defaultValue={selectedUser.fullName} /></label>
                        <label><span>Email</span><input name="email" defaultValue={selectedUser.email} /></label>
                        <label><span>Phone</span><input name="phone" defaultValue={selectedUser.phone || ""} /></label>
                        <label>
                          <span>Role</span>
                          <select name="role" defaultValue={selectedUser.role}>
                            <option value="Employee">Employee</option>
                            <option value="HR Officer">HR Officer</option>
                            <option value="Payroll Officer">Payroll Officer</option>
                          </select>
                        </label>
                        <label><span>Department</span><input name="department" defaultValue={selectedUser.department || ""} /></label>
                        <label><span>Designation</span><input name="designation" defaultValue={selectedUser.designation || ""} /></label>
                        <label><span>Joining Date</span><input type="date" name="dateOfJoining" defaultValue={selectedUser.dateOfJoining || ""} /></label>
                        <label><span>Status</span><input name="employmentStatus" defaultValue={selectedUser.employmentStatus || ""} /></label>
                        <label><span>Emergency Contact</span><input name="emergencyContact" defaultValue={selectedUser.emergencyContact || ""} /></label>
                        <label>
                          <span>Active</span>
                          <select name="active" defaultValue={String(selectedUser.active)}>
                            <option value="true">Active</option>
                            <option value="false">Inactive</option>
                          </select>
                        </label>
                        <label className="two-col-span"><span>Address</span><textarea name="address" defaultValue={selectedUser.address || ""} /></label>
                        <label className="two-col-span"><span>About</span><textarea name="about" defaultValue={selectedUser.about || ""} /></label>
                        <label className="two-col-span"><span>What I Love About My Job</span><textarea name="loveAboutJob" defaultValue={selectedUser.loveAboutJob || ""} /></label>
                        <label className="two-col-span"><span>Interests and Hobbies</span><textarea name="hobbies" defaultValue={selectedUser.hobbies || ""} /></label>
                        <button type="submit" className="button primary">Save User</button>
                      </form>
                    ) : (
                      <div className="empty-state">Choose a user from the table to edit details.</div>
                    )}
                  </article>
                  <article className="panel">
                    <div className="panel-actions">
                      <div>
                        <span className="eyebrow">Onboard</span>
                        <h3>Create Employee or Officer</h3>
                      </div>
                    </div>
                    <form
                      className="form-grid"
                      onSubmit={(event) => {
                        event.preventDefault();
                        handleCreateUser(Object.fromEntries(new FormData(event.currentTarget).entries()));
                      }}
                    >
                      <label><span>Full Name</span><input name="fullName" required /></label>
                      <div className="split-grid">
                        <label><span>Email</span><input type="email" name="email" required /></label>
                        <label><span>Phone</span><input name="phone" required /></label>
                      </div>
                      <div className="split-grid">
                        <label><span>Password</span><input type="password" name="password" required /></label>
                        <label><span>Employee ID</span><input name="employeeId" placeholder="EMP-010" /></label>
                      </div>
                      <div className="split-grid">
                        <label>
                          <span>Role</span>
                          <select name="role" defaultValue="Employee">
                            <option value="Employee">Employee</option>
                            <option value="HR Officer">HR Officer</option>
                            <option value="Payroll Officer">Payroll Officer</option>
                          </select>
                        </label>
                        <label><span>Month Wage</span><input type="number" name="monthWage" defaultValue="50000" /></label>
                      </div>
                      <div className="split-grid">
                        <label><span>Department</span><input name="department" /></label>
                        <label><span>Designation</span><input name="designation" /></label>
                      </div>
                      <button type="submit" className="button primary">Create User</button>
                    </form>
                  </article>
                </section>
              </>
            )}

            {state.view === "people" && (
              <section className="table-card">
                <div className="panel-actions">
                  <div>
                    <span className="eyebrow">Directory</span>
                    <h3>People Overview</h3>
                    <div className="table-note">HR and Payroll can view employee details and attendance snapshots only.</div>
                  </div>
                </div>
                <DirectoryTable employees={state.employees} />
              </section>
            )}

            {state.view === "attendance" && state.attendance && (
              <>
                <section className="panel-grid">
                  <article className="panel">
                    <div className="panel-actions">
                      <div>
                        <span className="eyebrow">Self Attendance</span>
                        <h3>Mark Your Own Attendance</h3>
                        <div className="table-note">Attendance uses manual date and time entry.</div>
                      </div>
                    </div>
                    <form
                      className="form-grid"
                      onSubmit={(event) => {
                        event.preventDefault();
                        const values = Object.fromEntries(new FormData(event.currentTarget).entries());
                        handleAttendanceMark({ ...values, action: event.nativeEvent.submitter?.value });
                      }}
                    >
                      <div className="split-grid">
                        <label><span>Date</span><input type="date" name="date" defaultValue={state.currentDate} required /></label>
                        <label><span>Time</span><input type="time" name="time" defaultValue="09:00" required /></label>
                      </div>
                      <div className="inline-actions">
                        <button type="submit" className="button primary" value="checkin">Check In</button>
                        <button type="submit" className="button secondary" value="checkout">Check Out</button>
                      </div>
                    </form>
                  </article>
                  <article className="panel">
                    <div className="panel-actions">
                      <div>
                        <span className="eyebrow">Attendance Filters</span>
                        <h3>View Logs</h3>
                      </div>
                    </div>
                    <form
                      className="form-grid"
                      key={`${state.attendanceFilter.employeeId}-${state.attendanceFilter.month}-${state.attendanceFilter.day}`}
                      onSubmit={(event) => {
                        event.preventDefault();
                        const values = Object.fromEntries(new FormData(event.currentTarget).entries());
                        loadAttendance({
                          month: values.month || state.currentMonth,
                          day: values.day || "",
                          employeeId: state.permissions.canViewAttendanceDirectory ? values.employeeId || visibleEmployeeId : state.me.id,
                        });
                      }}
                    >
                      {state.permissions.canViewAttendanceDirectory && (
                        <label>
                          <span>Employee</span>
                          <select name="employeeId" defaultValue={visibleEmployeeId}>
                            {state.employees.map((employee) => (
                              <option key={employee.id} value={employee.id}>
                                {employee.fullName} ({employee.role})
                              </option>
                            ))}
                          </select>
                        </label>
                      )}
                      <div className="split-grid">
                        <label><span>Month</span><input type="month" name="month" defaultValue={state.attendanceFilter.month} /></label>
                        <label><span>Specific Day</span><input type="date" name="day" defaultValue={state.attendanceFilter.day} /></label>
                      </div>
                      <button type="submit" className="button ghost">Apply Filters</button>
                    </form>
                    <div className="stat-block">
                      <span className="eyebrow">Summary</span>
                      <strong>{state.attendance.summary.payableDays} payable days</strong>
                      <div className="metric-subtext">
                        {state.attendance.summary.presentDays} present, {state.attendance.summary.absentDays} absent, {state.attendance.summary.extraHours} extra hours
                      </div>
                    </div>
                  </article>
                </section>
                <section className="table-card">
                  <div className="panel-actions">
                    <div>
                      <span className="eyebrow">Attendance Register</span>
                      <h3>{state.attendance.employee.fullName}</h3>
                    </div>
                  </div>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Date</th>
                          <th>Check In</th>
                          <th>Check Out</th>
                          <th>Working Hours</th>
                          <th>Extra Hours</th>
                          <th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {state.attendance.records.length ? (
                          state.attendance.records.map((record) => (
                            <tr key={`${record.employeeId}-${record.date}-${record.id}`}>
                              <td>{record.date}</td>
                              <td>{formatTime(record.checkIn)}</td>
                              <td>{formatTime(record.checkOut)}</td>
                              <td>{record.workedHours || 0}</td>
                              <td>{record.extraHours || 0}</td>
                              <td><Tag value={record.status} /></td>
                            </tr>
                          ))
                        ) : (
                          <tr><td colSpan="6" className="empty-state">No attendance records found for these filters.</td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </section>
              </>
            )}

            {state.view === "leave" && (
              <>
                <section className="panel-grid">
                  <article className="panel">
                    <div className="panel-actions">
                      <div>
                        <span className="eyebrow">Leave Request</span>
                        <h3>Apply for Time Off</h3>
                      </div>
                    </div>
                    <form
                      className="form-grid"
                      onSubmit={async (event) => {
                        event.preventDefault();
                        const values = Object.fromEntries(new FormData(event.currentTarget).entries());
                        if (state.role === "Employee") values.employeeId = state.me.id;
                        try {
                          await api("/api/leaves", { method: "POST", body: JSON.stringify(values) });
                          setStatus("Leave request submitted.", "success");
                          await loadView("leave");
                        } catch (error) {
                          setStatus(error.message, "error");
                        }
                      }}
                    >
                      {state.role !== "Employee" && (
                        <label>
                          <span>Employee</span>
                          <select name="employeeId" defaultValue={visibleEmployeeId}>
                            {state.employees.map((employee) => (
                              <option key={employee.id} value={employee.id}>
                                {employee.fullName}
                              </option>
                            ))}
                          </select>
                        </label>
                      )}
                      <label>
                        <span>Leave Type</span>
                        <select name="leaveTypeId">
                          {state.leaveTypes.map((type) => (
                            <option key={type.id} value={type.id}>
                              {type.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <div className="split-grid">
                        <label><span>Start Date</span><input type="date" name="startDate" defaultValue={state.currentDate} required /></label>
                        <label><span>End Date</span><input type="date" name="endDate" defaultValue={state.currentDate} required /></label>
                      </div>
                      <label><span>Reason</span><textarea name="reason" required /></label>
                      <button type="submit" className="button primary">Submit Request</button>
                    </form>
                  </article>
                  <article className="panel">
                    <div className="panel-actions">
                      <div>
                        <span className="eyebrow">Leave Balance</span>
                        <h3>Balance for Selected Employee</h3>
                      </div>
                    </div>
                    <div className="list">
                      {state.leaveBalances.map((balance) => (
                        <div className="list-item" key={balance.id}>
                          <strong>{balance.leaveTypeName}</strong>
                          <div className="metric-subtext">{balance.balance} days available</div>
                        </div>
                      ))}
                    </div>
                  </article>
                </section>
                <section className="table-card">
                  <div className="panel-actions">
                    <div>
                      <span className="eyebrow">Filters</span>
                      <h3>Leave History</h3>
                    </div>
                  </div>
                  <form
                    className="form-grid"
                    key={`${state.leaveFilter.employeeId}-${state.leaveFilter.month}-${state.leaveFilter.status}`}
                    onSubmit={(event) => {
                      event.preventDefault();
                      const values = Object.fromEntries(new FormData(event.currentTarget).entries());
                      loadLeaveData({
                        month: values.month || "",
                        status: values.status || "",
                        fromDate: values.fromDate || "",
                        toDate: values.toDate || "",
                        employeeId: state.role === "Employee" ? state.me.id : values.employeeId || "",
                      });
                    }}
                  >
                    {state.role !== "Employee" && (
                      <label>
                        <span>Employee</span>
                        <select name="employeeId" defaultValue={state.leaveFilter.employeeId}>
                          <option value="">All Employees</option>
                          {state.employees.map((employee) => (
                            <option key={employee.id} value={employee.id}>
                              {employee.fullName}
                            </option>
                          ))}
                        </select>
                      </label>
                    )}
                    <div className="form-grid two-col">
                      <label><span>Month</span><input type="month" name="month" defaultValue={state.leaveFilter.month} /></label>
                      <label>
                        <span>Status</span>
                        <select name="status" defaultValue={state.leaveFilter.status}>
                          <option value="">All Statuses</option>
                          {["Pending", "Approved", "Rejected", "Cancelled"].map((status) => (
                            <option key={status} value={status}>
                              {status}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label><span>From Date</span><input type="date" name="fromDate" defaultValue={state.leaveFilter.fromDate} /></label>
                      <label><span>To Date</span><input type="date" name="toDate" defaultValue={state.leaveFilter.toDate} /></label>
                    </div>
                    <button type="submit" className="button ghost">Apply Leave Filters</button>
                  </form>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Employee</th>
                          <th>Type</th>
                          <th>Dates</th>
                          <th>Days</th>
                          <th>Status</th>
                          <th>Reason</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {state.leaves.length ? (
                          state.leaves.map((leave) => (
                            <tr key={leave.id}>
                              <td>{leave.employeeName}</td>
                              <td>{leave.leaveTypeName}</td>
                              <td>{leave.startDate} to {leave.endDate}</td>
                              <td>{leave.days}</td>
                              <td><Tag value={leave.status} /></td>
                              <td>{leave.reason || "-"}</td>
                              <td>
                                {state.permissions.canReviewLeaves && leave.status === "Pending" ? (
                                  <div className="inline-actions">
                                    <button className="button ghost small" onClick={() => handleLeaveAction({ id: leave.id, action: "approve" })}>Approve</button>
                                    <button className="button ghost small" onClick={() => handleLeaveAction({ id: leave.id, action: "reject" })}>Reject</button>
                                  </div>
                                ) : state.permissions.canReviewLeaves && leave.status === "Approved" ? (
                                  <button className="button ghost small" onClick={() => handleLeaveAction({ id: leave.id, action: "cancel" })}>Cancel</button>
                                ) : (
                                  <span className="muted">No action</span>
                                )}
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr><td colSpan="7" className="empty-state">No leave records match the selected filters.</td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </section>
              </>
            )}

            {state.view === "payroll" && state.role === "Employee" && (
              <>
                <SalaryCard salaryInfo={currentSalaryStructure?.salaryInfo} title="My Salary Info" />
                <section className="table-card">
                  <div className="panel-actions">
                    <div>
                      <span className="eyebrow">Payslips</span>
                      <h3>My Payslip History</h3>
                    </div>
                    <form
                      className="inline-actions"
                      onSubmit={(event) => {
                        event.preventDefault();
                        const values = Object.fromEntries(new FormData(event.currentTarget).entries());
                        loadPayrollData({ ...state.payrollFilter, month: values.month, employeeId: state.me.id });
                      }}
                    >
                      <label><span>Month</span><input type="month" name="month" defaultValue={state.payrollFilter.month} /></label>
                      <button type="submit" className="button ghost">Load</button>
                    </form>
                  </div>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Month</th>
                          <th>Gross Pay</th>
                          <th>Total Deductions</th>
                          <th>Net Pay</th>
                          <th>Status</th>
                          <th>Download</th>
                        </tr>
                      </thead>
                      <tbody>
                        {state.payslips.length ? (
                          state.payslips.map((payslip) => (
                            <tr key={`${payslip.month}-${payslip.employeeId}`}>
                              <td>{payslip.month}</td>
                              <td>{formatCurrency(payslip.earnings.grossPay)}</td>
                              <td>{formatCurrency(payslip.deductions.totalDeductions)}</td>
                              <td>{formatCurrency(payslip.netPay)}</td>
                              <td><Tag value={payslip.status} /></td>
                              <td><button className="button ghost small" onClick={() => triggerPayslipDownload(state.me.id, payslip.month)}>Download</button></td>
                            </tr>
                          ))
                        ) : (
                          <tr><td colSpan="6" className="empty-state">No payslips available for the selected month.</td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </section>
              </>
            )}

            {state.view === "payroll" && state.role !== "Employee" && (
              <>
                <section className="panel-grid">
                  <article className="panel">
                    <div className="panel-actions">
                      <div>
                        <span className="eyebrow">Payroll Filters</span>
                        <h3>Payroll History and Payslips</h3>
                      </div>
                    </div>
                    <form
                      className="form-grid"
                      key={`${state.payrollFilter.employeeId}-${state.payrollFilter.month}-${state.payrollFilter.payrunStatus}`}
                      onSubmit={(event) => {
                        event.preventDefault();
                        const values = Object.fromEntries(new FormData(event.currentTarget).entries());
                        loadPayrollData({
                          month: values.month || state.currentMonth,
                          employeeId: values.employeeId || "",
                          payrunStatus: values.payrunStatus || "",
                        });
                      }}
                    >
                      <label>
                        <span>Employee</span>
                        <select name="employeeId" defaultValue={state.payrollFilter.employeeId}>
                          <option value="">All Employees</option>
                          {state.employees.map((employee) => (
                            <option key={employee.id} value={employee.id}>
                              {employee.fullName}
                            </option>
                          ))}
                        </select>
                      </label>
                      <div className="split-grid">
                        <label><span>Month</span><input type="month" name="month" defaultValue={state.payrollFilter.month} /></label>
                        <label>
                          <span>Payrun Status</span>
                          <select name="payrunStatus" defaultValue={state.payrollFilter.payrunStatus}>
                            <option value="">All Statuses</option>
                            <option value="Draft">Draft</option>
                            <option value="Locked">Locked</option>
                          </select>
                        </label>
                      </div>
                      <button type="submit" className="button ghost">Apply Payroll Filters</button>
                    </form>
                  </article>
                  <article className="panel">
                    <div className="panel-actions">
                      <div>
                        <span className="eyebrow">Payrun Engine</span>
                        <h3>Generate Monthly Payroll</h3>
                      </div>
                    </div>
                    <form
                      className="form-grid"
                      onSubmit={async (event) => {
                        event.preventDefault();
                        const values = Object.fromEntries(new FormData(event.currentTarget).entries());
                        try {
                          await api("/api/payruns/generate", { method: "POST", body: JSON.stringify(values) });
                          setStatus("Payrun generated.", "success");
                          await loadView("payroll");
                        } catch (error) {
                          setStatus(error.message, "error");
                        }
                      }}
                    >
                      <label><span>Payroll Month</span><input type="month" name="month" defaultValue={state.payrollFilter.month} /></label>
                      <button type="submit" className="button primary">Generate or Refresh Payrun</button>
                    </form>
                  </article>
                </section>
                <SalaryCard
                  salaryInfo={currentSalaryStructure?.salaryInfo}
                  title={`Salary Info - ${currentSalaryStructure?.employeeName || "Selected Employee"}`}
                />
                <section className="panel">
                  <div className="panel-actions">
                    <div>
                      <span className="eyebrow">Salary Structure</span>
                      <h3>Edit Salary Inputs</h3>
                    </div>
                  </div>
                  <form
                    key={currentSalaryStructure?.employeeId || "salary"}
                    className="form-grid two-col"
                    onSubmit={async (event) => {
                      event.preventDefault();
                      const form = Object.fromEntries(new FormData(event.currentTarget).entries());
                      const payload = { employeeId: form.employeeId };
                      Object.entries(form).forEach(([key, value]) => {
                        if (key !== "employeeId") payload[key] = Number(value || 0);
                      });
                      try {
                        await api("/api/payroll/structures", { method: "POST", body: JSON.stringify(payload) });
                        setStatus("Salary structure saved.", "success");
                        await loadView("payroll");
                      } catch (error) {
                        setStatus(error.message, "error");
                      }
                    }}
                  >
                    <label>
                      <span>Employee</span>
                      <select name="employeeId" defaultValue={currentSalaryStructure?.employeeId}>
                        {state.employees.map((employee) => (
                          <option key={employee.id} value={employee.id}>
                            {employee.fullName}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label><span>Month Wage</span><input type="number" name="monthWage" defaultValue={currentSalaryStructure?.monthWage || 50000} /></label>
                    <label><span>Working Days in a Week</span><input type="number" name="workingDaysPerWeek" defaultValue={currentSalaryStructure?.workingDaysPerWeek || 5} /></label>
                    <label><span>Break Time (hrs)</span><input type="number" step="0.5" name="breakHours" defaultValue={currentSalaryStructure?.breakHours || 1} /></label>
                    <label><span>Basic Salary %</span><input type="number" step="0.01" name="basicPercentage" defaultValue={currentSalaryStructure?.basicPercentage || 50} /></label>
                    <label><span>HRA %</span><input type="number" step="0.01" name="hraPercentage" defaultValue={currentSalaryStructure?.hraPercentage || 25} /></label>
                    <label><span>Standard Allowance %</span><input type="number" step="0.01" name="standardAllowancePercentage" defaultValue={currentSalaryStructure?.standardAllowancePercentage || 8.33} /></label>
                    <label><span>Performance Bonus %</span><input type="number" step="0.01" name="performanceBonusPercentage" defaultValue={currentSalaryStructure?.performanceBonusPercentage || 4.17} /></label>
                    <label><span>Leave Travel Allowance %</span><input type="number" step="0.01" name="leaveTravelAllowancePercentage" defaultValue={currentSalaryStructure?.leaveTravelAllowancePercentage || 4.17} /></label>
                    <label><span>Fixed Allowance %</span><input type="number" step="0.01" name="fixedAllowancePercentage" defaultValue={currentSalaryStructure?.fixedAllowancePercentage || 8.33} /></label>
                    <label><span>Employee PF %</span><input type="number" step="0.01" name="employeePfPercentage" defaultValue={currentSalaryStructure?.employeePfPercentage || 12} /></label>
                    <label><span>Employer PF %</span><input type="number" step="0.01" name="employerPfPercentage" defaultValue={currentSalaryStructure?.employerPfPercentage || 12} /></label>
                    <label><span>Professional Tax</span><input type="number" step="0.01" name="professionalTax" defaultValue={currentSalaryStructure?.professionalTax || 200} /></label>
                    <label><span>Other Deduction</span><input type="number" step="0.01" name="otherDeduction" defaultValue={currentSalaryStructure?.otherDeduction || 0} /></label>
                    <button type="submit" className="button primary">Save Salary Structure</button>
                  </form>
                </section>
                <section className="table-card">
                  <div className="panel-actions">
                    <div>
                      <span className="eyebrow">Payrun History</span>
                      <h3>Monthly Payroll Runs</h3>
                    </div>
                  </div>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr><th>Month</th><th>Status</th><th>Records</th><th>Generated At</th></tr>
                      </thead>
                      <tbody>
                        {state.payruns.length ? (
                          state.payruns.map((run) => (
                            <tr key={run.id}>
                              <td>{run.month}</td>
                              <td><Tag value={run.status} /></td>
                              <td>{run.records.length}</td>
                              <td>{formatDate(run.generatedAt)}</td>
                            </tr>
                          ))
                        ) : (
                          <tr><td colSpan="4" className="empty-state">No payrun history found.</td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </section>
              </>
            )}

            {state.view === "profile" && state.me && (
              <>
                <section className="panel">
                  <div className="profile-hero">
                    <div className="profile-avatar-wrap">
                      <div className="profile-avatar">
                        {state.me.profilePhoto ? <img src={state.me.profilePhoto} alt={state.me.fullName} /> : initialsFor(state.me.fullName)}
                      </div>
                      <label>
                        <span>Profile Photo</span>
                        <input type="file" accept="image/*" onChange={(event) => event.target.files?.[0] && handleProfilePhotoChange(event.target.files[0])} />
                      </label>
                      <div className="metric-subtext">Upload a square photo for the profile menu and your profile page.</div>
                    </div>
                    <div className="stack">
                      <div className="panel-actions">
                        <div>
                          <span className="eyebrow">My Profile</span>
                          <h3>{state.me.fullName}</h3>
                          <div className="table-note">{state.me.role} | {state.me.employeeId}</div>
                        </div>
                      </div>
                      <div className="profile-info-grid">
                        <div className="profile-info-item"><span className="eyebrow">Company</span><div>{state.me.companyName || state.settings.companyName}</div></div>
                        <div className="profile-info-item"><span className="eyebrow">Department</span><div>{state.me.department || "-"}</div></div>
                        <div className="profile-info-item"><span className="eyebrow">Login ID</span><div>{state.me.employeeId}</div></div>
                        <div className="profile-info-item"><span className="eyebrow">Manager</span><div>{state.me.manager || "-"}</div></div>
                        <div className="profile-info-item"><span className="eyebrow">Email</span><div>{state.me.email}</div></div>
                        <div className="profile-info-item"><span className="eyebrow">Location</span><div>{state.me.location || "-"}</div></div>
                        <div className="profile-info-item"><span className="eyebrow">Mobile</span><div>{state.me.phone || "-"}</div></div>
                        <div className="profile-info-item"><span className="eyebrow">Designation</span><div>{state.me.designation || "-"}</div></div>
                      </div>
                      <div className="profile-tabs">
                        <span className="profile-tab">Resume</span>
                        <span className="profile-tab">Private Info</span>
                        <span className="profile-tab">Salary Info</span>
                        <span className="profile-tab">Security</span>
                      </div>
                    </div>
                  </div>
                </section>
                <section className="profile-long-grid">
                  <article className="stack">
                    <div className="profile-story-card"><h4>About</h4><p className="profile-text">{state.me.about || ""}</p></div>
                    <div className="profile-story-card"><h4>What I Love About My Job</h4><p className="profile-text">{state.me.loveAboutJob || ""}</p></div>
                    <div className="profile-story-card"><h4>My Interests and Hobbies</h4><p className="profile-text">{state.me.hobbies || ""}</p></div>
                  </article>
                  <article className="stack">
                    <div className="profile-side-card"><h4>Skills</h4><p className="profile-text">{state.me.skills || ""}</p></div>
                    <div className="profile-side-card"><h4>Certification</h4><p className="profile-text">{state.me.certifications || ""}</p></div>
                  </article>
                </section>
                <section className="panel">
                  <div className="panel-actions">
                    <div><span className="eyebrow">Edit Profile</span><h3>Keep your information up to date</h3></div>
                  </div>
                  <form
                    key={state.me.id}
                    className="form-grid two-col"
                    onSubmit={(event) => {
                      event.preventDefault();
                      const values = Object.fromEntries(new FormData(event.currentTarget).entries());
                      handleProfileSave(values);
                    }}
                  >
                    <input type="hidden" name="id" value={state.me.id} />
                    <input type="hidden" name="profilePhoto" value={state.me.profilePhoto || ""} readOnly />
                    <label><span>Full Name</span><input name="fullName" defaultValue={state.me.fullName} disabled={state.role === "Employee"} /></label>
                    <label><span>Email</span><input name="email" defaultValue={state.me.email} disabled={state.role === "Employee"} /></label>
                    <label><span>Phone</span><input name="phone" defaultValue={state.me.phone || ""} /></label>
                    <label><span>Emergency Contact</span><input name="emergencyContact" defaultValue={state.me.emergencyContact || ""} /></label>
                    <label><span>Company</span><input name="companyName" defaultValue={state.me.companyName || ""} disabled={state.role !== "Admin"} /></label>
                    <label><span>Location</span><input name="location" defaultValue={state.me.location || ""} /></label>
                    <label><span>Department</span><input name="department" defaultValue={state.me.department || ""} disabled={state.role === "Employee"} /></label>
                    <label><span>Manager</span><input name="manager" defaultValue={state.me.manager || ""} disabled={!(state.role === "Admin" || state.role === "HR Officer")} /></label>
                    <label className="two-col-span"><span>Address</span><textarea name="address" defaultValue={state.me.address || ""} /></label>
                    <label className="two-col-span"><span>About</span><textarea name="about" defaultValue={state.me.about || ""} /></label>
                    <label className="two-col-span"><span>What I Love About My Job</span><textarea name="loveAboutJob" defaultValue={state.me.loveAboutJob || ""} /></label>
                    <label className="two-col-span"><span>My Interests and Hobbies</span><textarea name="hobbies" defaultValue={state.me.hobbies || ""} /></label>
                    <label className="two-col-span"><span>Skills</span><textarea name="skills" defaultValue={state.me.skills || ""} /></label>
                    <label className="two-col-span"><span>Certifications</span><textarea name="certifications" defaultValue={state.me.certifications || ""} /></label>
                    <button type="submit" className="button primary">Save Profile</button>
                  </form>
                </section>
                <SalaryCard salaryInfo={currentSalaryStructure?.salaryInfo} title="My Salary Info" />
              </>
            )}

            {state.view === "reports" && (
              <>
                <section className="panel report-panel">
                  <div className="panel-actions">
                    <div>
                      <span className="eyebrow">Export</span>
                      <h3>Reports</h3>
                    </div>
                  </div>
                  <form
                    className="form-grid"
                    onSubmit={(event) => {
                      event.preventDefault();
                      const values = Object.fromEntries(new FormData(event.currentTarget).entries());
                      loadReports(values.type, values.month);
                    }}
                  >
                    <div className="report-filter-grid">
                      <label>
                        <span>Report Type</span>
                        <select name="type" defaultValue={state.reportType}>
                          {["attendance", "leave", ...(state.permissions.canAccessPayroll ? ["payroll"] : []), "employees"].map((type) => (
                            <option key={type} value={type}>
                              {type}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label><span>Month</span><input type="month" name="month" defaultValue={state.currentMonth} /></label>
                      <div className="stat-block report-stat-card">
                        <span className="eyebrow">Rows</span>
                        <strong>{state.report?.rows?.length || 0}</strong>
                      </div>
                      <div className="stat-block report-stat-card report-workspace-card">
                        <span className="eyebrow">Workspace</span>
                        <strong>{state.settings.companyName}</strong>
                      </div>
                    </div>
                    <div className="report-actions">
                      <button type="submit" className="button primary">Load Report</button>
                      <button type="button" className="button ghost" onClick={() => downloadCsv(`empay-${state.reportType}-${state.currentMonth}.csv`, state.report?.rows || [])}>Download CSV</button>
                    </div>
                  </form>
                </section>
                <section className="table-card report-table-card">
                  <div className="panel-actions">
                    <div>
                      <span className="eyebrow">Preview</span>
                      <h3>{formatReportColumnLabel(state.reportType)} Report</h3>
                      <div className="table-note">{state.report?.rows?.length || 0} rows for {state.currentMonth}</div>
                    </div>
                  </div>
                  <div className="table-wrap report-table-wrap">
                    <table className="report-table">
                      <thead>
                        <tr>
                          {(state.report?.rows?.[0] ? Object.keys(state.report.rows[0]) : []).map((column) => (
                            <th className="report-col" key={column}>
                              <span className="report-col-label">{formatReportColumnLabel(column)}</span>
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {state.report?.rows?.length ? (
                          state.report.rows.map((row, rowIndex) => (
                            <tr key={rowIndex}>
                              {Object.keys(row).map((column) => (
                                <td className="report-cell" key={column}>
                                  {formatReportCell(column, row[column])}
                                </td>
                              ))}
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan="1" className="empty-state">
                              No data for the selected report.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </section>
              </>
            )}

            {state.view === "audit" && (
              <section className="table-card">
                <div className="panel-actions">
                  <div>
                    <span className="eyebrow">Audit</span>
                    <h3>System Activity</h3>
                  </div>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr><th>Time</th><th>Action</th><th>Target</th><th>Actor</th></tr>
                    </thead>
                    <tbody>
                      {state.auditLogs.length ? (
                        state.auditLogs.map((log) => (
                          <tr key={log.id}>
                            <td>{formatDate(log.createdAt)}</td>
                            <td>{log.action}</td>
                            <td>{log.targetType} | {log.targetId}</td>
                            <td>{log.actorId}</td>
                          </tr>
                        ))
                      ) : (
                        <tr><td colSpan="4" className="empty-state">No audit log entries available.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </section>
            )}
          </section>
        </main>
      </section>
    </>
  );
}

createRoot(document.getElementById("root")).render(<App />);
