import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "../styles.css";

const MAX_PROFILE_PHOTO_BYTES = 2 * 1024 * 1024;
const THEME_OPTIONS = [
  { id: "professional", name: "Professional", note: "Calm blue-grey for daily ERP work." },
  { id: "relaxed", name: "Purple", note: "Classic mauve palette for a softer workspace tone." },
  { id: "bright", name: "Bright", note: "Clear daylight palette for high-visibility work." },
  { id: "midnight", name: "Midnight", note: "Dark focus mode for long working sessions." },
];

function localDateKey(dateLike = new Date()) {
  const value = dateLike instanceof Date ? dateLike : new Date(dateLike);
  if (Number.isNaN(value.getTime())) {
    return "1970-01-01";
  }
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function localTimeKey(dateLike = new Date()) {
  const value = dateLike instanceof Date ? dateLike : new Date(dateLike);
  if (Number.isNaN(value.getTime())) {
    return "09:00";
  }
  const hours = String(value.getHours()).padStart(2, "0");
  const minutes = String(value.getMinutes()).padStart(2, "0");
  return `${hours}:${minutes}`;
}

function serverDateKey(value, fallback = localDateKey()) {
  const match = String(value || "").match(/^(\d{4}-\d{2}-\d{2})/);
  return match?.[1] || fallback;
}

function normalizeQuickAttendance(record, currentDate) {
  if (!record || record.date !== currentDate) {
    return null;
  }
  return record;
}

function createInitialState() {
  const today = localDateKey();
  const month = today.slice(0, 7);
  return {
    screen: "public",
    authMode: "login",
    status: { message: "", type: "info" },
    profileMenuOpen: false,
    csrfToken: "",
    toasts: [],
    profileTab: "resume",
    manageUserModalId: null,
    me: null,
    role: null,
    theme: "professional",
    settings: { companyName: "EmPay", companyLogo: "" },
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
    attendancePillBusy: false,
    serverNow: today,
    currentMonth: month,
    currentDate: today,
    attendanceFilter: { month, day: "", employeeId: "" },
    leaveFilter: { month, status: "", fromDate: "", toDate: "", employeeId: "" },
    payrollFilter: { month, employeeId: "", payrunStatus: "" },
    reportType: "attendance",
  };
}

const viewConfig = {
  dashboard: { label: "Dashboard", icon: "home", roles: ["Admin", "Employee", "HR Officer", "Payroll Officer"] },
  manageUsers: { label: "Manage Users", icon: "users", roles: ["Admin"] },
  people: { label: "People Directory", icon: "directory", roles: ["HR Officer", "Payroll Officer"] },
  attendance: { label: "Attendance", icon: "clock", roles: ["Admin", "Employee", "HR Officer", "Payroll Officer"] },
  leave: { label: "Leave", icon: "calendar", roles: ["Admin", "Employee", "HR Officer", "Payroll Officer"] },
  payroll: { label: "Payroll", icon: "wallet", roles: ["Admin", "Employee", "Payroll Officer"] },
  reports: { label: "Reports", icon: "chart", roles: ["Admin", "HR Officer", "Payroll Officer"] },
  profile: { label: "My Profile", icon: "profile", roles: ["Admin", "Employee", "HR Officer", "Payroll Officer"] },
  audit: { label: "Audit Log", icon: "shield", roles: ["Admin"] },
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

function sanitizeValues(values) {
  return Object.fromEntries(
    Object.entries(values).map(([key, value]) => [
      key,
      typeof value === "string" ? value.trim() : value,
    ])
  );
}

function makeToastId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function validatePasswordStrength(password) {
  const value = String(password || "");
  if (value.length < 12) {
    return "Password must be at least 12 characters long.";
  }
  if (!/[a-z]/.test(value) || !/[A-Z]/.test(value) || !/\d/.test(value) || !/[^A-Za-z0-9]/.test(value)) {
    return "Password must include uppercase, lowercase, number, and special character.";
  }
  return "";
}

async function api(path, options = {}) {
  const { csrfToken = "", ...fetchOptions } = options;
  const method = String(fetchOptions.method || "GET").toUpperCase();
  const headers = {
    ...(fetchOptions.headers || {}),
  };
  if (fetchOptions.body !== undefined && fetchOptions.body !== null && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  if (csrfToken && ["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    headers["X-CSRF-Token"] = csrfToken;
  }
  const response = await fetch(path, {
    credentials: "include",
    method,
    headers,
    ...fetchOptions,
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    throw new Error(payload?.error || payload?.detail || "Request failed");
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

function downloadExcel(filename, rows) {
  if (!rows.length) {
    return;
  }
  const headers = Object.keys(rows[0]);
  const table = [
    "<table>",
    "<thead><tr>",
    ...headers.map((header) => `<th>${formatReportColumnLabel(header)}</th>`),
    "</tr></thead>",
    "<tbody>",
    ...rows.map(
      (row) =>
        `<tr>${headers
          .map((header) => `<td>${String(formatReportCell(header, row[header])).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")}</td>`)
          .join("")}</tr>`
    ),
    "</tbody></table>",
  ].join("");
  const content = `<!DOCTYPE html><html><head><meta charset="utf-8" /></head><body>${table}</body></html>`;
  const blob = new Blob([content], { type: "application/vnd.ms-excel;charset=utf-8" });
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

function formatTimer(totalSeconds) {
  const safeSeconds = Math.max(Math.floor(Number(totalSeconds || 0)), 0);
  const hours = String(Math.floor(safeSeconds / 3600)).padStart(2, "0");
  const minutes = String(Math.floor((safeSeconds % 3600) / 60)).padStart(2, "0");
  const seconds = String(safeSeconds % 60).padStart(2, "0");
  return `${hours}:${minutes}:${seconds}`;
}

function attendanceActionState(record) {
  if (!record?.checkIn && !record?.currentSessionStart) {
    return { tone: "idle", label: "Check-in" };
  }
  if (record?.pauseStartedAt) {
    return { tone: "paused", label: "Resume" };
  }
  if (record?.currentSessionStart) {
    return { tone: "active", label: "Pause" };
  }
  if (record?.checkOut) {
    return { tone: "done", label: "Check-in" };
  }
  return { tone: "idle", label: "Check-in" };
}

function attendanceElapsedSeconds(record, nowValue) {
  if (!record?.checkIn && !record?.currentSessionStart) {
    return 0;
  }
  if (!record?.currentSessionStart) {
    return Math.max(Math.floor(Number(record.workedHours || 0) * 3600), 0);
  }
  const sessionStartTime = new Date(record.currentSessionStart).getTime();
  const accumulatedSeconds = Math.max(Number(record.accumulatedHours || 0) * 3600, 0);
  const pausedBaseSeconds = Math.max(Number(record.pausedMinutes || 0) * 60, 0);
  const currentPausedSeconds = record.pauseStartedAt
    ? Math.max((nowValue - new Date(record.pauseStartedAt).getTime()) / 1000, 0)
    : 0;
  const liveSeconds = Math.max((nowValue - sessionStartTime) / 1000 - pausedBaseSeconds - currentPausedSeconds, 0);
  return Math.max(Math.floor(accumulatedSeconds + liveSeconds), 0);
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    if (!file?.type?.startsWith("image/")) {
      reject(new Error("Please upload an image file."));
      return;
    }
    if (file.size > MAX_PROFILE_PHOTO_BYTES) {
      reject(new Error("Profile photo must be smaller than 2 MB."));
      return;
    }
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
    <section className="metrics-grid dashboard-metrics-grid">
      {cards.map((card) => (
        <article className={`metric-card dashboard-metric-card ${card.tone || ""}`} key={card.label}>
          <span className="eyebrow">{card.label}</span>
          <strong>{card.value}</strong>
          {card.note ? <div className={`dashboard-metric-note ${card.tone || ""}`}>{card.note}</div> : null}
        </article>
      ))}
    </section>
  );
}

function DashboardPanel({ title, children, subtitle = "", className = "" }) {
  return (
    <article className={`dashboard-panel ${className}`.trim()}>
      <div className="dashboard-panel-head">
        <div>
          <span className="eyebrow">{title}</span>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
      </div>
      {children}
    </article>
  );
}

function DashboardLegend({ items = [] }) {
  if (!items.length) {
    return null;
  }
  return (
    <div className="dashboard-legend">
      {items.map((item) => (
        <span key={item.label}>
          <i style={{ background: item.color }}></i>
          {item.label}
          {item.display ? ` ${item.display}` : ""}
        </span>
      ))}
    </div>
  );
}

function DashboardBarChart({ title, items = [], subtitle = "", compactLegend = false }) {
  const safeItems = items.filter((item) => Number(item?.value || 0) >= 0);
  const maxValue = Math.max(...safeItems.map((item) => Number(item.value || 0)), 1);
  return (
    <DashboardPanel title={title} subtitle={subtitle}>
      <DashboardLegend items={compactLegend ? safeItems : safeItems.map((item) => ({ ...item, display: "" }))} />
      <div className="dashboard-bar-chart">
        {safeItems.map((item) => (
          <div className="dashboard-bar-col" key={item.label}>
            <div className="dashboard-bar-track">
              <div
                className="dashboard-bar-fill"
                style={{
                  height: `${Math.max((Number(item.value || 0) / maxValue) * 100, Number(item.value || 0) > 0 ? 12 : 0)}%`,
                  background: item.color,
                }}
              ></div>
            </div>
            <strong>{item.label}</strong>
            <span>{item.display || item.value}</span>
          </div>
        ))}
      </div>
    </DashboardPanel>
  );
}

function DashboardHorizontalBars({ title, items = [], subtitle = "" }) {
  const maxValue = Math.max(...items.map((item) => Number(item.value || 0)), 1);
  return (
    <DashboardPanel title={title} subtitle={subtitle}>
      <div className="dashboard-horizontal-list">
        {items.map((item) => (
          <div className="dashboard-horizontal-row" key={item.label}>
            <span>{item.label}</span>
            <div className="dashboard-horizontal-track">
              <div
                className="dashboard-horizontal-fill"
                style={{ width: `${(Number(item.value || 0) / maxValue) * 100}%`, background: item.color }}
              ></div>
            </div>
            <strong>{item.display || item.value}</strong>
          </div>
        ))}
      </div>
    </DashboardPanel>
  );
}

function DashboardDonutChart({ title, items = [], subtitle = "" }) {
  const total = items.reduce((sum, item) => sum + Number(item.value || 0), 0);
  let cursor = 0;
  const gradient = items.length
    ? items
        .map((item) => {
          const start = (cursor / Math.max(total, 1)) * 360;
          cursor += Number(item.value || 0);
          const end = (cursor / Math.max(total, 1)) * 360;
          return `${item.color} ${start}deg ${end}deg`;
        })
        .join(", ")
    : "#2f3641 0deg 360deg";
  return (
    <DashboardPanel title={title} subtitle={subtitle}>
      <DashboardLegend items={items} />
      <div className="dashboard-donut-wrap">
        <div className="dashboard-donut" style={{ backgroundImage: `conic-gradient(${gradient})` }}>
          <div className="dashboard-donut-hole">
            <strong>{total}</strong>
            <span>Total</span>
          </div>
        </div>
      </div>
    </DashboardPanel>
  );
}

function DashboardLineChart({ title, series = [], subtitle = "" }) {
  const safeSeries = Array.isArray(series) ? series : [];
  const normalizedSeries =
    safeSeries.length && safeSeries[0]?.points
      ? safeSeries
      : [{ name: title, color: "#e3a641", points: safeSeries }];
  const labels = normalizedSeries[0]?.points?.map((point) => point.label) || [];
  const values = normalizedSeries.flatMap((item) => item.points.map((point) => Number(point.value || 0)));
  const maxValue = Math.max(...values, 1);
  const minValue = Math.min(...values, 0);
  const range = Math.max(maxValue - minValue, 1);
  const width = 520;
  const height = 220;
  const paddingX = 18;
  const paddingTop = 18;
  const paddingBottom = 28;
  const innerWidth = width - paddingX * 2;
  const innerHeight = height - paddingTop - paddingBottom;

  function pointString(points) {
    return points
      .map((point, index) => {
        const x = paddingX + (labels.length === 1 ? innerWidth / 2 : (innerWidth * index) / Math.max(labels.length - 1, 1));
        const y = paddingTop + innerHeight - ((Number(point.value || 0) - minValue) / range) * innerHeight;
        return `${x},${y}`;
      })
      .join(" ");
  }

  return (
    <DashboardPanel title={title} subtitle={subtitle}>
      <DashboardLegend items={normalizedSeries.map((item) => ({ label: item.name, color: item.color }))} />
      <div className="dashboard-line-shell">
        <svg viewBox={`0 0 ${width} ${height}`} className="dashboard-line-chart" preserveAspectRatio="none">
          {[0, 1, 2, 3].map((step) => {
            const y = paddingTop + (innerHeight / 3) * step;
            return <line key={step} x1={paddingX} x2={width - paddingX} y1={y} y2={y} className="dashboard-grid-line" />;
          })}
          {normalizedSeries.map((item) => (
            <g key={item.name}>
              <polyline points={pointString(item.points)} fill="none" stroke={item.color} strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
              {item.points.map((point, index) => {
                const x = paddingX + (labels.length === 1 ? innerWidth / 2 : (innerWidth * index) / Math.max(labels.length - 1, 1));
                const y = paddingTop + innerHeight - ((Number(point.value || 0) - minValue) / range) * innerHeight;
                return <circle key={`${item.name}-${point.label}`} cx={x} cy={y} r="4.5" fill={item.color} />;
              })}
            </g>
          ))}
        </svg>
        <div className="dashboard-axis-labels">
          {labels.map((label) => (
            <span key={label}>{label}</span>
          ))}
        </div>
      </div>
    </DashboardPanel>
  );
}

function SalaryCard({ salaryInfo, title }) {
  if (!salaryInfo) {
    return (
      <section className="salary-card salary-showcase">
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
    <section className="salary-card salary-showcase">
      <div className="salary-header">
        <div>
          <span className="eyebrow">Compensation</span>
          <h3>{title}</h3>
          <div className="table-note">A clean summary of your pay structure, benefits, and deductions.</div>
        </div>
        <Tag value="Salary Info" />
      </div>
      <div className="salary-grid">
        <div className="stack salary-panel-block">
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
          <div className="salary-panel-card">
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
        <div className="stack salary-panel-block">
          <div className="salary-panel-card">
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
          <div className="salary-panel-card">
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
            <Tag value="Unified workspace" />
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

function AuthScreen({ mode, onBack, onModeChange, onLogin, onSignup, onError }) {
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [companyLogo, setCompanyLogo] = useState("");
  const fileInputRef = useRef(null);

  async function handleLogoChange(file) {
    if (!file) {
      setCompanyLogo("");
      return;
    }
    const value = await readFileAsDataUrl(file);
    setCompanyLogo(value);
  }

  return (
    <section className="auth-shell auth-shell-compact">
      <div className="auth-card-compact card">
        <button className="back-link auth-back-link" onClick={onBack}>
          Back to landing
        </button>
        <div className="auth-logo-lockup">
          {companyLogo && mode === "signup" ? (
            <img className="auth-logo-preview" src={companyLogo} alt="Company logo preview" />
          ) : (
            <span className="brand-mark auth-brand-mark">odoo</span>
          )}
        </div>
        <div className="auth-helper-card">
          {mode === "login"
            ? "Access and manage your people operations, attendance, leave, and payroll."
            : "Create the workspace admin account first, then start onboarding your team."}
        </div>
        {mode === "login" ? (
            <form
              className="form-grid auth-form-compact"
            onSubmit={(event) => {
              event.preventDefault();
              onLogin(Object.fromEntries(new FormData(event.currentTarget).entries()));
            }}
            >
              <label>
                <span>Email</span>
                <input type="email" name="email" placeholder="Enter your email" autoComplete="username" required />
              </label>
              <label>
                <span className="auth-password-label">
                  <span>Password</span>
                </span>
                <div className="password-field">
                  <input
                    type={showPassword ? "text" : "password"}
                    name="password"
                    placeholder="Enter your password"
                    autoComplete="current-password"
                    required
                  />
                  <PasswordIconButton visible={showPassword} onClick={() => setShowPassword((prev) => !prev)} />
                </div>
              </label>
            <button type="submit" className="button primary auth-submit">
              Sign In
            </button>
            <p className="auth-switch auth-switch-center">
              Don&apos;t have an account?{" "}
              <button type="button" className="inline-link" onClick={() => onModeChange("signup")}>
                Sign up
              </button>
            </p>
          </form>
        ) : (
          <form
            className="form-grid auth-form-compact"
            onSubmit={async (event) => {
              event.preventDefault();
              const payload = Object.fromEntries(new FormData(event.currentTarget).entries());
              onSignup({ ...payload, companyLogo });
            }}
            >
            <div className="auth-logo-upload-row">
              <div className="auth-logo-lockup secondary">
                {companyLogo ? (
                  <img className="auth-logo-preview" src={companyLogo} alt="Company logo preview" />
                ) : (
                  <span className="auth-logo-placeholder">App/Web Logo</span>
                )}
              </div>
              <div className="auth-logo-upload-copy">
                <button
                  type="button"
                  className="button ghost small"
                  onClick={() => fileInputRef.current?.click()}
                >
                  Upload Logo
                </button>
                {companyLogo ? (
                  <button type="button" className="button ghost small" onClick={() => setCompanyLogo("")}>
                    Remove
                  </button>
                ) : null}
                <input
                  ref={fileInputRef}
                  className="hidden"
                  type="file"
                  accept="image/*"
                  onChange={async (event) => {
                    try {
                      await handleLogoChange(event.target.files?.[0]);
                    } catch (error) {
                      onError?.(error.message || "Could not read the selected image.");
                    } finally {
                      event.target.value = "";
                    }
                  }}
                />
              </div>
            </div>
            <label>
              <span>Company Name</span>
              <input name="companyName" placeholder="Enter company name" required />
            </label>
            <label>
              <span>Name</span>
              <input name="fullName" placeholder="Enter your name" required />
            </label>
            <label>
              <span>Email</span>
              <input type="email" name="email" placeholder="Enter your email" autoComplete="username" required />
            </label>
            <label>
              <span>Phone</span>
              <input name="phone" placeholder="Enter your phone number" required />
            </label>
            <label>
              <span className="auth-password-label">
                <span>Password</span>
              </span>
              <div className="password-field">
                <input
                  type={showPassword ? "text" : "password"}
                  name="password"
                  placeholder="Create a password"
                  autoComplete="new-password"
                  minLength="12"
                  required
                />
                <PasswordIconButton visible={showPassword} onClick={() => setShowPassword((prev) => !prev)} />
              </div>
            </label>
            <label>
              <span className="auth-password-label">
                <span>Confirm Password</span>
              </span>
              <div className="password-field">
                <input
                  type={showConfirmPassword ? "text" : "password"}
                  name="confirmPassword"
                  placeholder="Confirm your password"
                  autoComplete="new-password"
                  minLength="12"
                  required
                />
                <PasswordIconButton visible={showConfirmPassword} onClick={() => setShowConfirmPassword((prev) => !prev)} />
              </div>
            </label>
            <button type="submit" className="button primary auth-submit">
              Sign Up
            </button>
            <p className="auth-switch auth-switch-center">
              Already have an account?{" "}
              <button type="button" className="inline-link" onClick={() => onModeChange("login")}>
                Sign in
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

function AttendancePill({ record, onAction, busy = false }) {
  const [nowValue, setNowValue] = useState(() => Date.now());
  const clickTimerRef = useRef(null);
  const actionState = attendanceActionState(record);
  const elapsed = formatTimer(attendanceElapsedSeconds(record, nowValue));
  const toneText =
    actionState.tone === "done"
      ? "Checked out"
      : actionState.tone === "paused"
        ? "Paused"
        : actionState.tone === "active"
          ? "Working time"
          : "Ready";

  useEffect(() => {
    if (actionState.tone === "active" || actionState.tone === "paused") {
      const intervalId = window.setInterval(() => setNowValue(Date.now()), 1000);
      return () => window.clearInterval(intervalId);
    }
    setNowValue(Date.now());
    return undefined;
  }, [actionState.tone, record?.checkIn, record?.pauseStartedAt, record?.checkOut]);

  useEffect(
    () => () => {
      if (clickTimerRef.current) {
        window.clearTimeout(clickTimerRef.current);
      }
    },
    []
  );

    function handleClick() {
      if (busy) {
        return;
      }
      if (clickTimerRef.current) {
        window.clearTimeout(clickTimerRef.current);
      }
    clickTimerRef.current = window.setTimeout(() => {
      clickTimerRef.current = null;
      if (actionState.tone === "idle" || actionState.tone === "done") {
        onAction("checkin");
      } else if (actionState.tone === "active") {
        onAction("pause");
      } else if (actionState.tone === "paused") {
        onAction("resume");
      }
    }, 220);
  }

    function handleDoubleClick() {
      if (busy) {
        return;
      }
      if (clickTimerRef.current) {
        window.clearTimeout(clickTimerRef.current);
        clickTimerRef.current = null;
    }
    if (record?.checkIn && !record?.checkOut) {
      onAction("checkout");
    }
  }

  return (
    <button
      type="button"
        className={`attendance-pill ${actionState.tone}`}
        onClick={handleClick}
        onDoubleClick={handleDoubleClick}
        disabled={busy}
        title="Single click to check in, pause, or resume. Double click to check out."
      >
        <span className="attendance-pill-copy">
          <strong>{actionState.label}</strong>
          <span>{busy ? "Updating..." : toneText}</span>
        </span>
      <span className="attendance-pill-timer">{elapsed}</span>
    </button>
  );
}

function CompensationEditor({ employees, currentSalaryStructure, onSave }) {
  const [employeeId, setEmployeeId] = useState(String(currentSalaryStructure?.employeeId || employees[0]?.id || ""));
  const [monthWage, setMonthWage] = useState(Number(currentSalaryStructure?.monthWage || 50000));
  const [workingDaysPerWeek, setWorkingDaysPerWeek] = useState(Number(currentSalaryStructure?.workingDaysPerWeek || 5));
  const [breakHours, setBreakHours] = useState(Number(currentSalaryStructure?.breakHours || 1));
  const [employeePfPercentage, setEmployeePfPercentage] = useState(Number(currentSalaryStructure?.employeePfPercentage || 12));
  const [employerPfPercentage, setEmployerPfPercentage] = useState(Number(currentSalaryStructure?.employerPfPercentage || 12));
  const [professionalTax, setProfessionalTax] = useState(Number(currentSalaryStructure?.professionalTax || 200));
  const [otherDeduction, setOtherDeduction] = useState(Number(currentSalaryStructure?.otherDeduction || 0));
  const [percentages, setPercentages] = useState({
    basicPercentage: Number(currentSalaryStructure?.basicPercentage || 50),
    hraPercentage: Number(currentSalaryStructure?.hraPercentage || 25),
    standardAllowancePercentage: Number(currentSalaryStructure?.standardAllowancePercentage || 8.33),
    performanceBonusPercentage: Number(currentSalaryStructure?.performanceBonusPercentage || 4.17),
    leaveTravelAllowancePercentage: Number(currentSalaryStructure?.leaveTravelAllowancePercentage || 4.17),
    fixedAllowancePercentage: Number(currentSalaryStructure?.fixedAllowancePercentage || 8.33),
  });

  useEffect(() => {
    setEmployeeId(String(currentSalaryStructure?.employeeId || employees[0]?.id || ""));
    setMonthWage(Number(currentSalaryStructure?.monthWage || 50000));
    setWorkingDaysPerWeek(Number(currentSalaryStructure?.workingDaysPerWeek || 5));
    setBreakHours(Number(currentSalaryStructure?.breakHours || 1));
    setEmployeePfPercentage(Number(currentSalaryStructure?.employeePfPercentage || 12));
    setEmployerPfPercentage(Number(currentSalaryStructure?.employerPfPercentage || 12));
    setProfessionalTax(Number(currentSalaryStructure?.professionalTax || 200));
    setOtherDeduction(Number(currentSalaryStructure?.otherDeduction || 0));
    setPercentages({
      basicPercentage: Number(currentSalaryStructure?.basicPercentage || 50),
      hraPercentage: Number(currentSalaryStructure?.hraPercentage || 25),
      standardAllowancePercentage: Number(currentSalaryStructure?.standardAllowancePercentage || 8.33),
      performanceBonusPercentage: Number(currentSalaryStructure?.performanceBonusPercentage || 4.17),
      leaveTravelAllowancePercentage: Number(currentSalaryStructure?.leaveTravelAllowancePercentage || 4.17),
      fixedAllowancePercentage: Number(currentSalaryStructure?.fixedAllowancePercentage || 8.33),
    });
  }, [currentSalaryStructure, employees]);

  const componentRows = [
    {
      key: "basicPercentage",
      label: "Basic Salary",
      percentage: percentages.basicPercentage,
    },
    {
      key: "hraPercentage",
      label: "House Rent Allowance",
      percentage: percentages.hraPercentage,
    },
    {
      key: "standardAllowancePercentage",
      label: "Standard Allowance",
      percentage: percentages.standardAllowancePercentage,
    },
    {
      key: "performanceBonusPercentage",
      label: "Performance Bonus",
      percentage: percentages.performanceBonusPercentage,
    },
    {
      key: "leaveTravelAllowancePercentage",
      label: "Leave Travel Allowance",
      percentage: percentages.leaveTravelAllowancePercentage,
    },
    {
      key: "fixedAllowancePercentage",
      label: "Fixed Allowance",
      percentage: percentages.fixedAllowancePercentage,
    },
  ];

  return (
    <section className="panel compensation-panel">
      <div className="panel-actions">
        <div>
          <span className="eyebrow">Compensation</span>
          <h3>Edit Percentage and Value Inputs</h3>
        </div>
      </div>
      <form
        key={currentSalaryStructure?.employeeId || "compensation"}
        className="form-grid"
        onSubmit={(event) => {
          event.preventDefault();
          onSave({
            employeeId: Number(employeeId),
            monthWage,
            workingDaysPerWeek,
            breakHours,
            employeePfPercentage,
            employerPfPercentage,
            professionalTax,
            otherDeduction,
            ...percentages,
          });
        }}
      >
        <div className="split-grid">
          <label>
            <span>Employee</span>
            <select name="employeeId" value={employeeId} onChange={(event) => setEmployeeId(event.target.value)}>
              {employees.map((employee) => (
                <option key={employee.id} value={employee.id}>
                  {employee.fullName}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Month Wage</span>
            <input type="number" step="0.01" name="monthWage" value={monthWage} onChange={(event) => setMonthWage(Number(event.target.value || 0))} />
          </label>
        </div>
        <div className="split-grid">
          <label><span>Working Days / Week</span><input type="number" name="workingDaysPerWeek" value={workingDaysPerWeek} onChange={(event) => setWorkingDaysPerWeek(Number(event.target.value || 0))} /></label>
          <label><span>Break Hours</span><input type="number" step="0.5" name="breakHours" value={breakHours} onChange={(event) => setBreakHours(Number(event.target.value || 0))} /></label>
        </div>
        <div className="compensation-grid">
          {componentRows.map((row) => (
            <div className="comp-row" key={row.key}>
              <strong>{row.label}</strong>
              <label>
                <span>Percent</span>
                <input
                  type="number"
                  step="0.01"
                  name={row.key}
                  value={row.percentage}
                  onChange={(event) =>
                    setPercentages((prev) => ({
                      ...prev,
                      [row.key]: Number(event.target.value || 0),
                    }))
                  }
                />
              </label>
              <label>
                <span>Value</span>
                <input
                  className="static-input"
                  type="number"
                  step="0.01"
                  value={Number((monthWage * row.percentage) / 100).toFixed(2)}
                  readOnly
                />
              </label>
            </div>
          ))}
          <div className="comp-row">
            <strong>Provident Fund</strong>
            <label>
              <span>Employee PF %</span>
              <input type="number" step="0.01" name="employeePfPercentage" value={employeePfPercentage} onChange={(event) => setEmployeePfPercentage(Number(event.target.value || 0))} />
            </label>
            <label>
              <span>Employer PF %</span>
              <input type="number" step="0.01" name="employerPfPercentage" value={employerPfPercentage} onChange={(event) => setEmployerPfPercentage(Number(event.target.value || 0))} />
            </label>
          </div>
          <div className="comp-row">
            <strong>Deductions</strong>
            <label>
              <span>Professional Tax</span>
              <input type="number" step="0.01" name="professionalTax" value={professionalTax} onChange={(event) => setProfessionalTax(Number(event.target.value || 0))} />
            </label>
            <label>
              <span>Other Deduction</span>
              <input type="number" step="0.01" name="otherDeduction" value={otherDeduction} onChange={(event) => setOtherDeduction(Number(event.target.value || 0))} />
            </label>
          </div>
        </div>
        <button type="submit" className="button primary">Save Compensation</button>
      </form>
    </section>
  );
}

function Icon({ name, className = "" }) {
  const paths = {
    home: (
      <path d="M4 10.5 12 4l8 6.5V20h-5.5v-5h-5v5H4z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
    ),
    users: (
      <>
        <path d="M8.5 12a3 3 0 1 1 0-6 3 3 0 0 1 0 6Z" fill="none" stroke="currentColor" strokeWidth="1.8" />
        <path d="M15.5 11a2.5 2.5 0 1 1 0-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        <path d="M4.5 19a4.5 4.5 0 0 1 8 0" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        <path d="M14.5 18a3.5 3.5 0 0 1 4-2.7" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </>
    ),
    directory: (
      <>
        <rect x="5" y="4.5" width="14" height="15" rx="3" fill="none" stroke="currentColor" strokeWidth="1.8" />
        <path d="M8 8.5h8M8 12h8M8 15.5h5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </>
    ),
    clock: (
      <>
        <circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" strokeWidth="1.8" />
        <path d="M12 8v4.5l3 2" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </>
    ),
    calendar: (
      <>
        <rect x="4.5" y="6" width="15" height="13" rx="2.5" fill="none" stroke="currentColor" strokeWidth="1.8" />
        <path d="M8 4.5v3M16 4.5v3M4.5 9.5h15" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </>
    ),
    wallet: (
      <>
        <path d="M5 7.5A2.5 2.5 0 0 1 7.5 5H18v14H7.5A2.5 2.5 0 0 1 5 16.5z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
        <path d="M18 10.5h-4a1.5 1.5 0 0 0 0 3h4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      </>
    ),
    chart: (
      <>
        <path d="M5 19V9M12 19V5M19 19v-7" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        <path d="M4 19h16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </>
    ),
    profile: (
      <>
        <circle cx="12" cy="9" r="3.2" fill="none" stroke="currentColor" strokeWidth="1.8" />
        <path d="M5 19a7 7 0 0 1 14 0" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </>
    ),
    shield: (
      <path d="M12 4.5 18.5 7v5.4c0 3.8-2.6 6.4-6.5 7.9-3.9-1.5-6.5-4.1-6.5-7.9V7z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
    ),
    email: <path d="M4.5 7.5 12 13l7.5-5.5M5 6h14a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1Z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" />,
    phone: <path d="M8 5.5c.7 3.5 4 6.8 7.5 7.5l2-2c.4-.4 1-.5 1.5-.3l1.6.7c.6.2 1 .8 1 1.5V17c0 .8-.7 1.5-1.5 1.5C11.7 18.5 4.5 11.3 4.5 2.5 4.5 1.7 5.2 1 6 1h3.6c.7 0 1.3.4 1.5 1l.7 1.6c.2.5.1 1.1-.3 1.5z" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" />,
    user: <><circle cx="12" cy="8.5" r="3.2" fill="none" stroke="currentColor" strokeWidth="1.8" /><path d="M5 19a7 7 0 0 1 14 0" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></>,
    role: <path d="M12 4.5 18.5 7v5.4c0 3.8-2.6 6.4-6.5 7.9-3.9-1.5-6.5-4.1-6.5-7.9V7zM9.2 12l1.8 1.8 3.8-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />,
    department: <><path d="M5 19V7.5h14V19M3.5 19h17M8 10.5h2M14 10.5h2M8 14h2M14 14h2M10 19v-3h4v3" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></>,
    briefcase: <path d="M8.5 6V4.8A1.8 1.8 0 0 1 10.3 3h3.4a1.8 1.8 0 0 1 1.8 1.8V6m-11 2h15v8a2 2 0 0 1-2 2h-11a2 2 0 0 1-2-2z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" />,
    date: <><rect x="4.5" y="6" width="15" height="13" rx="2.5" fill="none" stroke="currentColor" strokeWidth="1.8" /><path d="M8 4.5v3M16 4.5v3M4.5 9.5h15" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></>,
    location: <path d="M12 20c3.5-4 5.2-7 5.2-9.3A5.2 5.2 0 0 0 6.8 10.7C6.8 13 8.5 16 12 20Zm0-7.5a1.9 1.9 0 1 0 0-3.8 1.9 1.9 0 0 0 0 3.8Z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />,
    emergency: <><path d="M12 3.8 19.2 7v5.3c0 4.1-2.8 6.8-7.2 8.2-4.4-1.4-7.2-4.1-7.2-8.2V7z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" /><path d="M12 8v5M12 16h.01" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></>,
    active: <path d="M12 20a8 8 0 1 0-8-8m8 8a8 8 0 0 0 8-8M8.8 12.2l2 2 4.4-4.4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />,
    address: <><path d="M6 7.5h12M6 12h12M6 16.5h8" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /><rect x="4.5" y="4.5" width="15" height="15" rx="3" fill="none" stroke="currentColor" strokeWidth="1.8" /></>,
    about: <><circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" strokeWidth="1.8" /><path d="M12 10v4M12 7.6h.01" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></>,
    heart: <path d="M12 19s-6.5-4.2-8-8.1C2.7 7.5 4.9 5 7.9 5c1.8 0 3.1 1 4.1 2.3C13 6 14.3 5 16.1 5c3 0 5.2 2.5 3.9 5.9-1.5 3.9-8 8.1-8 8.1Z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />,
    hobby: <path d="M7.5 7.5c2-2 5-2 7 0s2 5 0 7-5 2-7 0-2-5 0-7Zm-2.8 8.3-1.2 4 4-1.2m10.5-10.5 1.5-1.5a2.1 2.1 0 1 0-3-3L15 5.1" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />,
    skills: <path d="M14.5 4.5 19.5 9.5l-8.9 8.9-5.7 1.2 1.2-5.7zM12 7l5 5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" />,
    certificate: <><path d="M8 4.5h8v8H8zM9.5 16l2.5-1.5 2.5 1.5V12H9.5z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" /><path d="M10 8h4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></>,
    company: <><path d="M5 19V7.5h14V19M3.5 19h17M8 10.5h2M14 10.5h2M8 14h2M14 14h2" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></>,
    manager: <><circle cx="12" cy="8" r="3" fill="none" stroke="currentColor" strokeWidth="1.8" /><path d="M6 19c.6-2.8 3-4.5 6-4.5s5.4 1.7 6 4.5M18 8h3M19.5 6.5V9.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></>,
    photo: <><rect x="4.5" y="6" width="15" height="12" rx="2.5" fill="none" stroke="currentColor" strokeWidth="1.8" /><circle cx="10" cy="11" r="2" fill="none" stroke="currentColor" strokeWidth="1.8" /><path d="m13 15 2-2 2.5 2.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></>,
    lock: <><rect x="6.5" y="10.5" width="11" height="8" rx="2" fill="none" stroke="currentColor" strokeWidth="1.8" /><path d="M8.5 10.5V8.7a3.5 3.5 0 1 1 7 0v1.8" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></>,
    plus: <path d="M12 5v14M5 12h14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />,
    eye: <><path d="M2.8 12s3.3-5.2 9.2-5.2 9.2 5.2 9.2 5.2-3.3 5.2-9.2 5.2S2.8 12 2.8 12Z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" /><circle cx="12" cy="12" r="2.4" fill="none" stroke="currentColor" strokeWidth="1.8" /></>,
    eyeOff: <><path d="m4 4 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /><path d="M2.8 12s3.3-5.2 9.2-5.2c2.1 0 3.9.7 5.4 1.6M21.2 12s-3.3 5.2-9.2 5.2c-2.1 0-3.9-.7-5.4-1.6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" /><path d="M13.7 13.7A2.4 2.4 0 0 1 10.3 10.3" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></>,
    trash: <><path d="M5.5 7h13M9 7V5.5h6V7M8 9.5v7M12 9.5v7M16 9.5v7M7 7h10l-.8 12a1.5 1.5 0 0 1-1.5 1.4h-5.4A1.5 1.5 0 0 1 7.8 19z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></>,
  };
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      {paths[name] || paths.about}
    </svg>
  );
}

function PasswordIconButton({ visible, onClick }) {
  return (
    <button type="button" className="icon-button" onClick={onClick} aria-label={visible ? "Hide password" : "Show password"}>
      <Icon name={visible ? "eyeOff" : "eye"} className="mini-icon" />
    </button>
  );
}

function FieldLabel({ icon, children, action = null }) {
  return (
    <span className="field-label">
      <span className="field-icon"><Icon name={icon} className="field-icon-svg" /></span>
      <span>{children}</span>
      {action}
    </span>
  );
}

function ToastViewport({ toasts }) {
  return (
    <div className="toast-stack" aria-live="polite" aria-atomic="true">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast ${toast.type}`}>
          <span className="toast-mark">{toast.type === "success" ? "OK" : "ER"}</span>
          <div className="toast-copy">
            <strong>{toast.type === "success" ? "Success" : "Error"}</strong>
            <span>{toast.message}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function ModalShell({ title, onClose, children }) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(event) => event.stopPropagation()}>
        <div className="panel-actions">
          <div>
            <span className="eyebrow">User Detail</span>
            <h3>{title}</h3>
          </div>
          <button type="button" className="button ghost small" onClick={onClose}>
            Close
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function UserDetailModal({ user, onClose, onSave, onDelete }) {
  if (!user) {
    return null;
  }
  return (
    <ModalShell title={user.fullName} onClose={onClose}>
      <form
        key={user.id}
        className="form-grid two-col"
        onSubmit={(event) => {
          event.preventDefault();
          onSave(Object.fromEntries(new FormData(event.currentTarget).entries()));
        }}
      >
        <input type="hidden" name="id" value={user.id} />
        <label><FieldLabel icon="user">Full Name</FieldLabel><input name="fullName" defaultValue={user.fullName} /></label>
        <label><FieldLabel icon="email">Email</FieldLabel><input name="email" defaultValue={user.email} /></label>
        <label><FieldLabel icon="phone">Phone</FieldLabel><input name="phone" defaultValue={user.phone || ""} /></label>
        <label>
          <FieldLabel icon="role">Role</FieldLabel>
          <select name="role" defaultValue={user.role}>
            <option value="Employee">Employee</option>
            <option value="HR Officer">HR Officer</option>
            <option value="Payroll Officer">Payroll Officer</option>
          </select>
        </label>
        <label><FieldLabel icon="department">Department</FieldLabel><input name="department" defaultValue={user.department || ""} /></label>
        <label><FieldLabel icon="briefcase">Designation</FieldLabel><input name="designation" defaultValue={user.designation || ""} /></label>
        <label><FieldLabel icon="date">Joining Date</FieldLabel><input type="date" name="dateOfJoining" defaultValue={user.dateOfJoining || ""} /></label>
        <label><FieldLabel icon="location">Location</FieldLabel><input name="location" defaultValue={user.location || ""} /></label>
        <label><FieldLabel icon="emergency">Emergency Contact</FieldLabel><input name="emergencyContact" defaultValue={user.emergencyContact || ""} /></label>
        <label>
          <FieldLabel icon="active">Active</FieldLabel>
          <select name="active" defaultValue={String(user.active)}>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
        </label>
        <label className="two-col-span"><FieldLabel icon="address">Address</FieldLabel><textarea name="address" defaultValue={user.address || ""} /></label>
        <label className="two-col-span"><FieldLabel icon="about">About</FieldLabel><textarea name="about" defaultValue={user.about || ""} /></label>
        <label className="two-col-span"><FieldLabel icon="heart">What I Love About My Job</FieldLabel><textarea name="loveAboutJob" defaultValue={user.loveAboutJob || ""} /></label>
        <label className="two-col-span"><FieldLabel icon="hobby">Interests and Hobbies</FieldLabel><textarea name="hobbies" defaultValue={user.hobbies || ""} /></label>
        <div className="inline-actions modal-actions-row two-col-span">
          <button type="submit" className="button primary">Save User</button>
          <button type="button" className="button ghost danger-button" onClick={() => onDelete?.(user)}>
            <Icon name="trash" className="mini-icon" />
            Delete User
          </button>
        </div>
      </form>
    </ModalShell>
  );
}

function DashboardView({ dashboard, role, settings }) {
  return (
    <section className="dashboard-shell">
      <div className="dashboard-shell-head">
        <div>
          <span className="eyebrow">Workspace Intelligence</span>
          <h2>{settings.companyName}</h2>
          <p>{role} overview tailored to the current workspace data.</p>
        </div>
      </div>
      <Metrics cards={dashboard.cards || []} />

      {dashboard.variant === "admin" && (
        <>
          <section className="dashboard-row split">
            <DashboardBarChart title="Headcount by department" items={dashboard.headcountByDepartment || []} compactLegend />
            <DashboardDonutChart title="Leave type distribution" items={dashboard.leaveTypeDistribution || []} />
          </section>
          <section className="dashboard-row">
            <DashboardLineChart
              title="Monthly payroll trend"
              subtitle="Gross payroll across the last five months."
              series={[{ name: "Payroll", color: "#e3a641", points: dashboard.monthlyPayrollTrend || [] }]}
            />
          </section>
          <section className="dashboard-row">
            <DashboardHorizontalBars
              title="Attendance rate by department"
              items={dashboard.attendanceRateByDepartment || []}
            />
          </section>
        </>
      )}

      {dashboard.variant === "hr" && (
        <>
          <section className="dashboard-row split">
            <DashboardLineChart
              title="Weekly attendance"
              subtitle="Check-ins recorded this week."
              series={[{ name: "Attendance", color: "#58a47b", points: dashboard.weeklyAttendance || [] }]}
            />
            <DashboardDonutChart title="Leave status breakdown" items={dashboard.leaveStatusBreakdown || []} />
          </section>
          <section className="dashboard-row">
            <DashboardBarChart title="Absenteeism rate by department" items={dashboard.absenteeismRateByDepartment || []} />
          </section>
          <section className="dashboard-row">
            <DashboardLineChart
              title="Headcount growth"
              subtitle="Active staff progression over the last five months."
              series={[{ name: "Headcount", color: "#5d84cf", points: dashboard.headcountGrowth || [] }]}
            />
          </section>
        </>
      )}

      {dashboard.variant === "payroll" && (
        <>
          <section className="dashboard-row split">
            <DashboardDonutChart title="Deductions breakdown" items={dashboard.deductionBreakdown || []} />
            <DashboardBarChart title="Net payroll by department" items={dashboard.netPayrollByDepartment || []} />
          </section>
          <section className="dashboard-row">
            <DashboardLineChart
              title="Gross vs net payroll trend"
              subtitle="Payroll movement across the last five months."
              series={[
                { name: "Gross", color: "#e3a641", points: dashboard.grossVsNetTrend?.gross || [] },
                { name: "Net", color: "#58a47b", points: dashboard.grossVsNetTrend?.net || [] },
              ]}
            />
          </section>
          <section className="dashboard-row">
            <DashboardBarChart title="Time-off approvals by week" items={dashboard.timeOffApprovalsByWeek || []} />
          </section>
        </>
      )}

      {dashboard.variant === "employee" && (
        <>
          <section className="dashboard-row split">
            <DashboardDonutChart title="Attendance this month" items={dashboard.attendanceThisMonth || []} />
            <DashboardHorizontalBars title="Leave balance by type" items={dashboard.leaveBalanceByType || []} />
          </section>
          <section className="dashboard-row">
            <DashboardBarChart title="Salary breakdown" items={dashboard.salaryBreakdown || []} />
          </section>
          <section className="dashboard-row">
            <DashboardLineChart
              title="Net salary trend"
              subtitle="Latest processed payroll values over time."
              series={[{ name: "Net salary", color: "#e3a641", points: dashboard.netSalaryTrend || [] }]}
            />
          </section>
        </>
      )}
    </section>
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
  const toastTimersRef = useRef(new Map());
  const profilePhotoInputRef = useRef(null);

  const availableViews = useMemo(
    () =>
      Object.entries(viewConfig)
        .filter(([, config]) => state.role && config.roles.includes(state.role))
        .map(([key, config]) => ({ key, ...config })),
    [state.role]
  );

  const visibleEmployeeId = state.role === "Employee" ? state.me?.id : state.selectedUserId || state.me?.id;
  const selectedUser = state.employees.find((employee) => employee.id === visibleEmployeeId) || state.employees[0];
  const manageUser = state.employees.find((employee) => employee.id === state.manageUserModalId) || null;
  const currentSalaryStructure = state.salaryStructures[0] || null;
  const currentAttendanceRecord = state.quickAttendance;

  function setStatus(message = "", type = "info") {
    const normalizedType = type === "error" || type === "danger" ? "error" : "success";
    if (!message) {
      setState((prev) => ({ ...prev, status: { message: "", type: normalizedType } }));
      return;
    }
    const id = makeToastId();
    setState((prev) => ({
      ...prev,
      status: { message, type: normalizedType },
      toasts: [...prev.toasts, { id, message, type: normalizedType }],
    }));
    const timeoutId = window.setTimeout(() => {
      setState((prev) => ({
        ...prev,
        toasts: prev.toasts.filter((toast) => toast.id !== id),
      }));
      toastTimersRef.current.delete(id);
    }, 3000);
    toastTimersRef.current.set(id, timeoutId);
  }

    async function bootstrap() {
      try {
        const auth = await api("/api/auth/me");
        const resolvedDate = localDateKey();
        const resolvedMonth = resolvedDate.slice(0, 7);
        setState((prev) => ({
          ...prev,
          screen: "app",
        csrfToken: auth.csrfToken || "",
        me: auth.user,
        role: auth.role,
        serverNow: auth.serverNow || prev.serverNow,
        currentDate: resolvedDate,
        currentMonth: resolvedMonth,
        settings: auth.settings || prev.settings,
        permissions: auth.permissions || {},
        selectedUserId: auth.user.id,
        attendanceFilter: { ...prev.attendanceFilter, employeeId: auth.user.id, month: resolvedMonth },
        leaveFilter: { ...prev.leaveFilter, employeeId: auth.user.id, month: resolvedMonth },
        payrollFilter: { ...prev.payrollFilter, employeeId: auth.user.id, month: resolvedMonth },
      }));
      await loadView("dashboard", {
        me: auth.user,
        role: auth.role,
        serverNow: auth.serverNow,
        currentDate: resolvedDate,
        currentMonth: resolvedMonth,
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
      const resolvedDate = localDateKey();
      const resolvedMonth = resolvedDate.slice(0, 7);
      const payload = await api(
        `/api/attendance?${query({
          employeeId: me.id,
          month: resolvedMonth,
        day: resolvedDate,
      })}`
    );
      const record = normalizeQuickAttendance(payload.records[0] || null, resolvedDate);
      setState((prev) => ({ ...prev, quickAttendance: record, attendancePillBusy: false }));
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
    const storedTheme = window.localStorage.getItem("empay-theme");
    if (storedTheme && THEME_OPTIONS.some((theme) => theme.id === storedTheme)) {
      setState((prev) => ({ ...prev, theme: storedTheme }));
    }
  }, []);

  useEffect(
    () => () => {
      toastTimersRef.current.forEach((timeoutId) => window.clearTimeout(timeoutId));
      toastTimersRef.current.clear();
    },
    []
  );

  useEffect(() => {
    document.documentElement.dataset.theme = state.theme || "pearl";
    window.localStorage.setItem("empay-theme", state.theme || "pearl");
  }, [state.theme]);

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
      const payload = sanitizeValues(values);
      const auth = await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setState((prev) => ({ ...prev, csrfToken: auth.csrfToken || "" }));
      setStatus("Login successful.", "success");
      await bootstrap();
    } catch (error) {
      setStatus(error.message, "error");
    }
  }

  async function handleSignup(values) {
    try {
      const payload = sanitizeValues(values);
      const passwordError = validatePasswordStrength(payload.password);
      if (passwordError) {
        setStatus(passwordError, "error");
        return;
      }
      const auth = await api("/api/auth/signup", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setState((prev) => ({ ...prev, csrfToken: auth.csrfToken || "" }));
      setStatus("Workspace created successfully.", "success");
      await bootstrap();
    } catch (error) {
      setStatus(error.message, "error");
    }
  }

  async function handleLogout() {
    await api("/api/auth/logout", { method: "POST", csrfToken: state.csrfToken });
    setState(createInitialState());
  }

  async function handleQuickAttendance(values) {
    try {
      await api("/api/attendance/mark", {
        method: "POST",
        body: JSON.stringify(values),
        csrfToken: state.csrfToken,
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
      const payload = sanitizeValues(values);
      const passwordError = validatePasswordStrength(payload.password);
      if (passwordError) {
        setStatus(passwordError, "error");
        return;
      }
      await api("/api/employees", {
        method: "POST",
        body: JSON.stringify(payload),
        csrfToken: state.csrfToken,
      });
      setStatus("New user created.", "success");
      await loadView("manageUsers");
    } catch (error) {
      setStatus(error.message, "error");
    }
  }

  async function handleUpdateUser(values) {
    try {
      const payload = sanitizeValues(values);
      await api(`/api/employees/${values.id}`, {
        method: "PUT",
        body: JSON.stringify({ ...payload, active: payload.active === "true" }),
        csrfToken: state.csrfToken,
      });
      setStatus("User updated successfully.", "success");
      await loadView("manageUsers");
      return true;
    } catch (error) {
      setStatus(error.message, "error");
      return false;
    }
  }

  async function handleDeleteUser(user) {
    if (!user?.id) {
      return;
    }
    if (!window.confirm(`Delete ${user.fullName}? This will remove the user and related records.`)) {
      return;
    }
    try {
      await api(`/api/employees/${user.id}`, {
        method: "DELETE",
        csrfToken: state.csrfToken,
      });
      setStatus("User deleted successfully.", "success");
      setState((prev) => ({ ...prev, manageUserModalId: null, selectedUserId: null }));
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
        csrfToken: state.csrfToken,
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
        csrfToken: state.csrfToken,
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
      setStatus("Profile photo selected.", "success");
    } catch (error) {
      setStatus(error.message || "Could not read the selected image.", "error");
    }
  }

  async function handleRemoveProfilePhoto() {
    try {
      await api(`/api/employees/${state.me.id}`, {
        method: "PUT",
        body: JSON.stringify({ profilePhoto: "" }),
        csrfToken: state.csrfToken,
      });
      setState((prev) => ({
        ...prev,
        me: { ...prev.me, profilePhoto: "" },
      }));
      setStatus("Profile photo removed.", "success");
    } catch (error) {
      setStatus(error.message, "error");
    }
  }

  function handleThemeChange(themeId) {
    setState((prev) => ({ ...prev, theme: themeId }));
    setStatus(`${THEME_OPTIONS.find((theme) => theme.id === themeId)?.name || "Theme"} applied.`, "success");
  }

    async function handleAttendancePillAction(action) {
      if (state.attendancePillBusy) {
        return;
      }
      const now = new Date();
      const today = localDateKey(now);
      const month = today.slice(0, 7);
      setState((prev) => ({ ...prev, attendancePillBusy: true }));
      try {
        await api("/api/attendance/mark", {
          method: "POST",
          body: JSON.stringify({
            action,
            date: today,
            time: localTimeKey(now),
          }),
          csrfToken: state.csrfToken,
        });
        setStatus(
          action === "checkin"
            ? "Checked in successfully."
            : action === "checkout"
              ? "Checked out successfully."
              : action === "pause"
                ? "Timer paused."
                : "Timer resumed.",
          "success"
        );
        await loadQuickAttendance({ ...state, currentDate: today, currentMonth: month });
        if (state.view === "attendance" || state.view === "dashboard") {
          await loadView(state.view);
        }
      } catch (error) {
        setStatus(error.message, "error");
        await loadQuickAttendance({ ...state, currentDate: today, currentMonth: month });
      } finally {
        setState((prev) => ({ ...prev, attendancePillBusy: false }));
      }
    }

  async function handleProfileSave(values) {
    try {
      const payload = sanitizeValues(values);
      await api(`/api/employees/${state.me.id}`, {
        method: "PUT",
        body: JSON.stringify(payload),
        csrfToken: state.csrfToken,
      });
      setStatus("Profile updated.", "success");
      await bootstrap();
      await loadView("profile");
    } catch (error) {
      setStatus(error.message, "error");
    }
  }

  async function handleChangePassword(values) {
    try {
      const payload = sanitizeValues(values);
      const passwordError = validatePasswordStrength(payload.newPassword);
      if (passwordError) {
        setStatus(passwordError, "error");
        return;
      }
      await api("/api/auth/change-password", {
        method: "POST",
        body: JSON.stringify(payload),
        csrfToken: state.csrfToken,
      });
      setStatus("Password changed successfully.", "success");
    } catch (error) {
      setStatus(error.message, "error");
    }
  }

  async function handleCreateLeaveType(values) {
    try {
      const payload = sanitizeValues(values);
      await api("/api/leave-types", {
        method: "POST",
        body: JSON.stringify(payload),
        csrfToken: state.csrfToken,
      });
      setStatus("Leave type created.", "success");
      await loadView("leave");
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
        <ToastViewport toasts={state.toasts} />
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
          onBack={() => setState((prev) => ({ ...prev, screen: "public" }))}
          onModeChange={(authMode) => setState((prev) => ({ ...prev, authMode }))}
          onLogin={handleLogin}
          onSignup={handleSignup}
          onError={(message) => setStatus(message, "error")}
        />
        <ToastViewport toasts={state.toasts} />
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
            <div className="sidebar-brand">
              <div className="sidebar-logo-shell">
                {state.settings.companyLogo ? (
                  <img className="brand-logo" src={state.settings.companyLogo} alt={state.settings.companyName} />
                ) : (
                  <span className="brand-mark">EmPay</span>
                )}
              </div>
              <div className="sidebar-brand-copy sidebar-text">
                <strong className="sidebar-company-name">{state.settings.companyName}</strong>
                <span className="muted sidebar-company-tag">People OS</span>
              </div>
            </div>
          </div>
          <nav className="nav">
            {availableViews.map((item) => (
              <button
                key={item.key}
                className={state.view === item.key ? "active" : ""}
                onClick={() => loadView(item.key)}
                title={item.label}
              >
                <span className="nav-icon"><Icon name={item.icon} className="nav-icon-svg" /></span>
                <span className="sidebar-text">{item.label}</span>
              </button>
            ))}
          </nav>
        </aside>
        <main className="app-main">
          <header className="app-header">
            <div>
              <span className="eyebrow">Workspace</span>
              <h1>{viewConfig[state.view]?.label || "Dashboard"}</h1>
            </div>
            <div className="header-right">
                {state.role === "Employee" && (
                 <AttendancePill
                   record={currentAttendanceRecord}
                   onAction={handleAttendancePillAction}
                   busy={state.attendancePillBusy}
                 />
                )}
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
                  <DirectoryTable employees={state.employees} onSelect={(id) => setState((prev) => ({ ...prev, manageUserModalId: id }))} showAction />
                </section>
                <section className="panel">
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
                        <label><span>Password</span><input type="password" name="password" autoComplete="new-password" minLength="12" required /></label>
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
                      <div className="split-grid">
                        <label><span>Location</span><input name="location" defaultValue="Bengaluru" /></label>
                        <label><span>Joining Date</span><input type="date" name="dateOfJoining" defaultValue={state.currentDate} /></label>
                      </div>
                      <button type="submit" className="button primary">Create User</button>
                    </form>
                </section>
                <UserDetailModal
                  user={manageUser}
                  onClose={() => setState((prev) => ({ ...prev, manageUserModalId: null }))}
                  onSave={async (values) => {
                    const ok = await handleUpdateUser(values);
                    if (ok) {
                      setState((prev) => ({ ...prev, manageUserModalId: null }));
                    }
                  }}
                  onDelete={handleDeleteUser}
                />
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
                <section className="table-card">
                  <div className="table-card-head">
                    <div>
                      <span className="eyebrow">Attendance Register</span>
                      <h3>{state.attendance.employee.fullName}</h3>
                      <div className="table-note">
                        {state.role === "Employee"
                          ? "Use the compact attendance pill near your profile photo to control check-in, pause, resume, and checkout."
                          : "Review filtered attendance logs for the selected employee or month."}
                      </div>
                    </div>
                  </div>
                  <form
                    className="attendance-toolbar"
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
                    <div className="attendance-filter-fields">
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
                      <label><span>Month</span><input type="month" name="month" defaultValue={state.attendanceFilter.month} /></label>
                      <label><span>Specific Day</span><input type="date" name="day" defaultValue={state.attendanceFilter.day} /></label>
                    </div>
                    <div className="attendance-toolbar-actions">
                      <div className="toolbar">
                        <button type="submit" className="button ghost">Apply</button>
                        <button
                          type="button"
                          className="button ghost"
                          onClick={() =>
                            loadAttendance({
                              month: state.currentMonth,
                              day: state.currentDate,
                              employeeId: state.permissions.canViewAttendanceDirectory ? visibleEmployeeId : state.me.id,
                            })
                          }
                        >
                          Today
                        </button>
                        <button
                          type="button"
                          className="button ghost"
                          onClick={() =>
                            loadAttendance({
                              month: state.currentMonth,
                              day: "",
                              employeeId: state.permissions.canViewAttendanceDirectory ? visibleEmployeeId : state.me.id,
                            })
                          }
                        >
                          This Month
                        </button>
                        <button
                          type="button"
                          className="button ghost"
                          onClick={() =>
                            loadAttendance({
                              month: state.currentMonth,
                              day: "",
                              employeeId: state.permissions.canViewAttendanceDirectory ? "" : state.me.id,
                            })
                          }
                        >
                          Reset
                        </button>
                      </div>
                    </div>
                  </form>
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
                          await api("/api/leaves", {
                            method: "POST",
                            body: JSON.stringify(values),
                            csrfToken: state.csrfToken,
                          });
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
                    {state.role === "Admin" && (
                      <form
                        className="form-grid admin-inline-form"
                        onSubmit={(event) => {
                          event.preventDefault();
                          handleCreateLeaveType(Object.fromEntries(new FormData(event.currentTarget).entries()));
                          event.currentTarget.reset();
                        }}
                      >
                        <div>
                          <span className="eyebrow">Admin</span>
                          <h3>Create Leave Type</h3>
                        </div>
                        <div className="split-grid">
                          <label>
                            <FieldLabel icon="plus">Leave Type Name</FieldLabel>
                            <input name="name" placeholder="Optional Holiday" required />
                          </label>
                          <label>
                            <FieldLabel icon="calendar">Default Balance</FieldLabel>
                            <input type="number" step="0.5" name="defaultBalance" defaultValue="0" required />
                          </label>
                        </div>
                        <button type="submit" className="button ghost">Create Leave Type</button>
                      </form>
                    )}
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
                              <td><button className="button ghost small" onClick={() => triggerPayslipDownload(state.me.id, payslip.month)}>Download PDF</button></td>
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
                          await api("/api/payruns/generate", {
                            method: "POST",
                            body: JSON.stringify(values),
                            csrfToken: state.csrfToken,
                          });
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
                <CompensationEditor
                  employees={state.employees}
                  currentSalaryStructure={currentSalaryStructure}
                  onSave={async (payload) => {
                    try {
                      await api("/api/payroll/structures", {
                        method: "POST",
                        body: JSON.stringify(payload),
                        csrfToken: state.csrfToken,
                      });
                      setStatus("Compensation saved.", "success");
                      await loadView("payroll");
                    } catch (error) {
                      setStatus(error.message, "error");
                    }
                  }}
                />
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
                      <div className="profile-avatar profile-avatar-large">
                        {state.me.profilePhoto ? <img src={state.me.profilePhoto} alt={state.me.fullName} /> : initialsFor(state.me.fullName)}
                      </div>
                      <input
                        ref={profilePhotoInputRef}
                        className="hidden"
                        type="file"
                        accept="image/*"
                        onChange={(event) => event.target.files?.[0] && handleProfilePhotoChange(event.target.files[0])}
                      />
                      <div className="photo-actions-card">
                        <div>
                          <span className="eyebrow">Profile Photo</span>
                          <div className="metric-subtext">Upload a clean square image for your profile and header avatar.</div>
                        </div>
                        <div className="photo-actions-row">
                          <button type="button" className="button ghost small" onClick={() => profilePhotoInputRef.current?.click()}>
                            {state.me.profilePhoto ? "Change Photo" : "Upload Photo"}
                          </button>
                          {state.me.profilePhoto ? (
                            <button type="button" className="button ghost small danger-button" onClick={handleRemoveProfilePhoto}>
                              Remove
                            </button>
                          ) : null}
                        </div>
                      </div>
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
                    </div>
                  </div>
                </section>
                <section className="profile-tabs-panel panel">
                  <div className="profile-tabs profile-tabs-large">
                    {[
                      ["resume", "Resume"],
                      ["personal", "Personal Info"],
                      ["salary", "Salary Info"],
                      ["security", "Security"],
                    ].map(([key, label]) => (
                      <button
                        key={key}
                        type="button"
                        className={`profile-tab ${state.profileTab === key ? "active" : ""}`}
                        onClick={() => setState((prev) => ({ ...prev, profileTab: key }))}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </section>
                {state.profileTab === "resume" && (
                  <section className="panel">
                    <div className="panel-actions">
                      <div><span className="eyebrow">Resume</span><h3>Show your strengths clearly</h3></div>
                    </div>
                    <form
                      key={`resume-${state.me.id}`}
                      className="form-grid"
                      onSubmit={(event) => {
                        event.preventDefault();
                        const values = Object.fromEntries(new FormData(event.currentTarget).entries());
                        handleProfileSave({ ...values, id: state.me.id, profilePhoto: state.me.profilePhoto || "", companyLogo: state.settings.companyLogo || "" });
                      }}
                    >
                      <label><FieldLabel icon="about">About</FieldLabel><textarea name="about" defaultValue={state.me.about || ""} /></label>
                      <label><FieldLabel icon="heart">What I Love About My Job</FieldLabel><textarea name="loveAboutJob" defaultValue={state.me.loveAboutJob || ""} /></label>
                      <label><FieldLabel icon="hobby">My Interests and Hobbies</FieldLabel><textarea name="hobbies" defaultValue={state.me.hobbies || ""} /></label>
                      <label><FieldLabel icon="skills">Skills</FieldLabel><textarea name="skills" defaultValue={state.me.skills || ""} /></label>
                      <label><FieldLabel icon="certificate">Certifications</FieldLabel><textarea name="certifications" defaultValue={state.me.certifications || ""} /></label>
                      <button type="submit" className="button primary">Save Resume</button>
                    </form>
                  </section>
                )}
                {state.profileTab === "personal" && (
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
                      <input type="hidden" name="companyLogo" value={state.settings.companyLogo || ""} readOnly />
                      <label><FieldLabel icon="user">Full Name</FieldLabel><input name="fullName" defaultValue={state.me.fullName} disabled={state.role === "Employee"} /></label>
                      <label><FieldLabel icon="email">Email</FieldLabel><input name="email" defaultValue={state.me.email} disabled={state.role === "Employee"} /></label>
                      <label><FieldLabel icon="phone">Phone</FieldLabel><input name="phone" defaultValue={state.me.phone || ""} /></label>
                      <label><FieldLabel icon="emergency">Emergency Contact</FieldLabel><input name="emergencyContact" defaultValue={state.me.emergencyContact || ""} /></label>
                      <label><FieldLabel icon="company">Company</FieldLabel><input name="companyName" defaultValue={state.me.companyName || ""} disabled={state.role !== "Admin"} /></label>
                      <label><FieldLabel icon="location">Location</FieldLabel><input name="location" defaultValue={state.me.location || ""} /></label>
                      <label><FieldLabel icon="department">Department</FieldLabel><input name="department" defaultValue={state.me.department || ""} disabled={state.role === "Employee"} /></label>
                      <label><FieldLabel icon="manager">Manager</FieldLabel><input name="manager" defaultValue={state.me.manager || ""} disabled={!(state.role === "Admin" || state.role === "HR Officer")} /></label>
                      <label className="two-col-span"><FieldLabel icon="address">Address</FieldLabel><textarea name="address" defaultValue={state.me.address || ""} /></label>
                      <button type="submit" className="button primary">Save Profile</button>
                    </form>
                  </section>
                )}
                {state.profileTab === "salary" && (
                  <SalaryCard salaryInfo={currentSalaryStructure?.salaryInfo} title="My Salary Info" />
                )}
                {state.profileTab === "security" && (
                  <section className="panel">
                    <div className="panel-actions">
                      <div><span className="eyebrow">Security</span><h3>Update your password</h3></div>
                    </div>
                    <div className="security-shell">
                      <form
                        className="form-grid security-form-card"
                        onSubmit={(event) => {
                          event.preventDefault();
                          handleChangePassword(Object.fromEntries(new FormData(event.currentTarget).entries()));
                          event.currentTarget.reset();
                        }}
                      >
                        <div>
                          <span className="eyebrow">Password</span>
                          <h3>Protect your account</h3>
                        </div>
                        <label><FieldLabel icon="lock">Current Password</FieldLabel><input type="password" name="currentPassword" autoComplete="current-password" required /></label>
                        <label><FieldLabel icon="lock">New Password</FieldLabel><input type="password" name="newPassword" autoComplete="new-password" minLength="12" required /></label>
                        <label><FieldLabel icon="lock">Confirm Password</FieldLabel><input type="password" name="confirmPassword" autoComplete="new-password" minLength="12" required /></label>
                        <button type="submit" className="button primary">Change Password</button>
                      </form>
                      <div className="security-side-stack">
                        <article className="profile-side-card security-theme-card">
                          <span className="eyebrow">Appearance</span>
                          <h3>Choose a workspace tone</h3>
                          <div className="table-note">Pick the palette that fits how you work through long ERP sessions.</div>
                          <div className="theme-grid">
                            {THEME_OPTIONS.map((theme) => (
                              <button
                                key={theme.id}
                                type="button"
                                className={`theme-option ${state.theme === theme.id ? "active" : ""}`}
                                onClick={() => handleThemeChange(theme.id)}
                              >
                                <span className={`theme-swatch ${theme.id}`}></span>
                                <strong>{theme.name}</strong>
                                <span>{theme.note}</span>
                              </button>
                            ))}
                          </div>
                        </article>
                        <article className="profile-side-card security-tips-card">
                          <span className="eyebrow">Security Tips</span>
                          <h3>Keep your access clean</h3>
                          <div className="table-note">A few simple habits keep the workspace safe and easier to trust.</div>
                          <div className="list">
                            <div className="list-item">Use a unique password with uppercase, lowercase, numbers, and symbols.</div>
                            <div className="list-item">Update your profile photo so colleagues can recognize your account quickly.</div>
                            <div className="list-item">Review your theme and profile details regularly for a cleaner workspace.</div>
                          </div>
                        </article>
                      </div>
                    </div>
                  </section>
                )}
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
                      <button type="button" className="button ghost" onClick={() => downloadExcel(`empay-${state.reportType}-${state.currentMonth}.xls`, state.report?.rows || [])}>Download Excel</button>
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
      <ToastViewport toasts={state.toasts} />
    </>
  );
}

createRoot(document.getElementById("root")).render(<App />);
