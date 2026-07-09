import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  MenuItem,
  TextField,
  Button,
  Grid,
  Chip,
  CircularProgress,
  Alert,
  Divider,
  LinearProgress,
  Tooltip,
  Tabs,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
} from '@mui/material';
import {
  BarChart3,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  TrendingUp,
  FileSpreadsheet,
  Zap,
  ShieldAlert,
  Clock,
  IndianRupee,
  FileText,
  Activity,
  History,
} from 'lucide-react';
import api from '../api';

interface InvoiceSummary {
  invoice_id?: string;
  invoice_number: string;
  invoice_date: string;
  billing_month?: string;
  billing_year?: number;
  vendor_name?: string;
  status: string;
  ledger_status?: string;
  billed_amount: number;
  approved_amount: number;
  rejected_amount?: number;
  fraud_amount?: number;
  record_count: number;
  remarks?: string;
}

interface ReconciliationSummary {
  invoice_number: string;
  invoice_date: string;
  overall_status: string;
  total_rows: number;
  billed_total: number;
  approved_total: number;
  rejected_total: number;
  pending_total: number;
  money_saved: number;
  approved_count: number;
  rejected_count: number;
  exception_count: number;
  pending_count: number;
  fraud_count: number;
  error_count: number;
  warning_count: number;
  auto_approved?: boolean;
}

const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const map: Record<string, { color: 'success' | 'error' | 'warning' | 'info' | 'default'; label: string }> = {
    APPROVED:  { color: 'success', label: 'APPROVED' },
    EXCEPTION: { color: 'error',   label: 'EXCEPTION' },
    PENDING:   { color: 'default', label: 'PENDING' },
    VALIDATED: { color: 'info',    label: 'VALIDATED' },
    MIXED:     { color: 'warning', label: 'MIXED' },
  };
  const cfg = map[status] ?? { color: 'default', label: status };
  return (
    <Chip
      label={cfg.label}
      color={cfg.color}
      size="small"
      sx={{ fontWeight: 800, letterSpacing: '0.06em', fontSize: '0.7rem', height: 22 }}
    />
  );
};

interface KpiCardProps {
  label: string;
  value: string;
  sub?: string;
  icon: React.ReactNode;
  accentColor: string;
  glowColor: string;
}

const KpiCard: React.FC<KpiCardProps> = ({ label, value, sub, icon, accentColor, glowColor }) => (
  <Card
    sx={{
      background: `linear-gradient(135deg, rgba(${glowColor},0.08) 0%, rgba(0,0,0,0) 70%)`,
      border: `1px solid rgba(${glowColor},0.18)`,
      boxShadow: `0 0 20px rgba(${glowColor},0.05)`,
      transition: 'transform 0.2s, box-shadow 0.2s',
      '&:hover': { transform: 'translateY(-2px)', boxShadow: `0 4px 24px rgba(${glowColor},0.15)` },
    }}
  >
    <CardContent sx={{ p: 2.5 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1.5 }}>
        <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', fontSize: '0.65rem' }}>
          {label}
        </Typography>
        <Box sx={{ p: 0.8, borderRadius: 1.5, background: `rgba(${glowColor},0.12)`, color: accentColor }}>
          {icon}
        </Box>
      </Box>
      <Typography variant="h5" sx={{ fontWeight: 800, color: '#fff', lineHeight: 1.2 }}>
        {value}
      </Typography>
      {sub && (
        <Typography variant="caption" sx={{ color: 'text.secondary', mt: 0.5, display: 'block' }}>
          {sub}
        </Typography>
      )}
    </CardContent>
  </Card>
);

export const Reconciliation: React.FC = () => {
  const [invoices, setInvoices] = useState<InvoiceSummary[]>([]);
  const [selectedInvoice, setSelectedInvoice] = useState('');
  const [summary, setSummary] = useState<ReconciliationSummary | null>(null);
  const [loadingInvoices, setLoadingInvoices] = useState(false);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [runningPipeline, setRunningPipeline] = useState(false);
  const [pipelineStep, setPipelineStep] = useState(0); // 0=idle 1=validate 2=approve 3=done
  const [statusMsg, setStatusMsg] = useState<{ type: 'success' | 'error' | 'warning'; text: string } | null>(null);

  // New states
  const [currentTab, setCurrentTab] = useState(0);
  const [compareA, setCompareA] = useState('');
  const [compareB, setCompareB] = useState('');
  const [comparisonResult, setComparisonResult] = useState<any | null>(null);
  const [comparing, setComparing] = useState(false);
  const [compareError, setCompareError] = useState('');

  // Fetch invoice list
  const fetchInvoices = useCallback(async () => {
    try {
      setLoadingInvoices(true);
      const res = await api.get('/invoices');
      setInvoices(res.data);
      if (res.data.length > 0 && !selectedInvoice) {
        setSelectedInvoice(res.data[0].invoice_number);
      }
    } catch {
      // silently ignore
    } finally {
      setLoadingInvoices(false);
    }
  }, [selectedInvoice]);

  // Fetch reconciliation summary for selected invoice
  const fetchSummary = useCallback(async (invNo: string) => {
    if (!invNo) return;
    try {
      setLoadingSummary(true);
      const res = await api.get(`/reconciliation/summary/${invNo}`);
      setSummary(res.data);
    } catch {
      setSummary(null);
    } finally {
      setLoadingSummary(false);
    }
  }, []);

  useEffect(() => { fetchInvoices(); }, [fetchInvoices]);
  useEffect(() => {
    if (selectedInvoice) fetchSummary(selectedInvoice);
  }, [selectedInvoice, fetchSummary]);

  const handleRunReconciliation = async () => {
    if (!selectedInvoice) return;
    try {
      setRunningPipeline(true);
      setStatusMsg(null);
      setPipelineStep(1);

      await new Promise(r => setTimeout(r, 600));
      setPipelineStep(2);

      const res = await api.post(`/reconciliation/run/${selectedInvoice}`);
      setPipelineStep(3);

      const data: ReconciliationSummary & { auto_approved?: boolean; validation?: any } = res.data;
      setSummary(data);

      if (data.auto_approved) {
        setStatusMsg({
          type: 'success',
          text: `✅ Reconciliation complete. Invoice auto-approved. Money saved: ₹${data.money_saved?.toLocaleString() ?? 0}.`,
        });
      } else if (data.fraud_count > 0 || data.error_count > 0) {
        setStatusMsg({
          type: 'warning',
          text: `⚠️ Reconciliation complete. Found ${data.fraud_count} fraud and ${data.error_count} errors — invoice held in EXCEPTION. Review violations before approving.`,
        });
      } else {
        setStatusMsg({ type: 'success', text: '✅ Reconciliation complete with warnings only. Review before approving.' });
      }

      await fetchInvoices();
    } catch (err: any) {
      setStatusMsg({ type: 'error', text: err.response?.data?.detail || 'Reconciliation failed.' });
    } finally {
      setRunningPipeline(false);
      setTimeout(() => setPipelineStep(0), 1500);
    }
  };

  const handleCompare = async () => {
    if (!compareA || !compareB) return;
    try {
      setComparing(true);
      setCompareError('');
      const res = await api.get(`/invoices/compare/${compareA}/${compareB}`);
      setComparisonResult(res.data);
    } catch (err: any) {
      setCompareError(err.response?.data?.detail || 'Comparison failed.');
      setComparisonResult(null);
    } finally {
      setComparing(false);
    }
  };

  const handleDownload = (endpoint: string) => {
    window.location.href = `http://127.0.0.1:8000/api${endpoint}`;
  };

  const fmt = (n: number) => `₹${(n ?? 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

  const reports = [
    {
      label: 'Approved Invoice',
      desc: 'All trainee rows with approved payouts > ₹0.',
      icon: <CheckCircle2 size={20} />,
      color: 'success' as const,
      accentRgb: '16,185,129',
      global: false,
      endpoint: () => `/reports/approved-invoice/${selectedInvoice}`,
    },
    {
      label: 'Corrected Invoice',
      desc: 'Side-by-side billed vs approved amounts with correction reasons.',
      icon: <AlertTriangle size={20} />,
      color: 'warning' as const,
      accentRgb: '245,158,11',
      global: false,
      endpoint: () => `/reports/corrected-invoice/${selectedInvoice}`,
    },
    {
      label: 'Rejected Invoice',
      desc: 'Fully rejected rows with reason codes and violation details.',
      icon: <XCircle size={20} />,
      color: 'error' as const,
      accentRgb: '239,68,68',
      global: false,
      endpoint: () => `/reports/rejected-invoice/${selectedInvoice}`,
    },
    {
      label: 'Exception Report',
      desc: 'All WARNING and ERROR rule violations for this invoice.',
      icon: <AlertTriangle size={20} />,
      color: 'warning' as const,
      accentRgb: '245,158,11',
      global: false,
      endpoint: () => `/reports/exceptions?invoice_number=${selectedInvoice}`,
    },
    {
      label: 'Payment Summary',
      desc: 'Per-trainee lifetime disbursements and remaining caps.',
      icon: <IndianRupee size={20} />,
      color: 'primary' as const,
      accentRgb: '99,102,241',
      global: false,
      endpoint: () => `/reports/payment-summary?invoice_number=${selectedInvoice}`,
    },
    {
      label: 'Vendor Payment Summary',
      desc: 'Per-trainee cumulative payouts and remaining headroom for this invoice.',
      icon: <IndianRupee size={20} />,
      color: 'success' as const,
      accentRgb: '16,185,129',
      global: false,
      endpoint: () => `/reports/vendor-payment-summary/${selectedInvoice}`,
    },
    {
      label: 'Fraud Report',
      desc: 'All FRAUD-classified incidents with reason codes and recommended actions.',
      icon: <ShieldAlert size={20} />,
      color: 'error' as const,
      accentRgb: '239,68,68',
      global: false,
      endpoint: () => `/reports/fraud?invoice_number=${selectedInvoice}`,
    },
    {
      label: 'Finance Summary',
      desc: 'Aggregate billed vs approved vs rejected totals with money saved.',
      icon: <BarChart3 size={20} />,
      color: 'secondary' as const,
      accentRgb: '6,182,212',
      global: false,
      endpoint: () => `/reports/finance-summary?invoice_number=${selectedInvoice}`,
    },
    {
      label: 'Invoice History Report',
      desc: 'Excel sheet listing all uploaded invoices with amounts, statuses, and counts.',
      icon: <FileSpreadsheet size={20} />,
      color: 'primary' as const,
      accentRgb: '99,102,241',
      global: true,
      endpoint: () => `/reports/invoice-history`,
    },
    {
      label: 'Monthly Billing Summary',
      desc: 'Grouped monthly statistics of billed, approved, and fraud amounts.',
      icon: <BarChart3 size={20} />,
      color: 'secondary' as const,
      accentRgb: '6,182,212',
      global: true,
      endpoint: () => `/reports/monthly-billing-summary`,
    },
    {
      label: 'Duplicate Billing Report',
      desc: 'All duplicate employee, distribution date, or kit claims across invoices.',
      icon: <ShieldAlert size={20} />,
      color: 'error' as const,
      accentRgb: '239,68,68',
      global: true,
      endpoint: () => `/reports/duplicate-billing`,
    },
    {
      label: 'Repeated Payment Report',
      desc: 'Items already paid in ledger but claimed again in other invoices.',
      icon: <XCircle size={20} />,
      color: 'error' as const,
      accentRgb: '239,68,68',
      global: true,
      endpoint: () => `/reports/repeated-payments`,
    },
    {
      label: 'Outstanding Payment Report',
      desc: 'Trainees with difference between billed and approved amounts.',
      icon: <AlertTriangle size={20} />,
      color: 'warning' as const,
      accentRgb: '245,158,11',
      global: true,
      endpoint: () => `/reports/outstanding-payments`,
    },
    {
      label: 'Vendor Summary Report',
      desc: 'Aggregate invoice counts and amounts grouped by vendor name.',
      icon: <BarChart3 size={20} />,
      color: 'success' as const,
      accentRgb: '16,185,129',
      global: true,
      endpoint: () => `/reports/vendor-summary`,
    },
    {
      label: 'Employee Billing History',
      desc: 'Comprehensive billing claims history log for all active/inactive employees.',
      icon: <History size={20} />,
      color: 'primary' as const,
      accentRgb: '99,102,241',
      global: true,
      endpoint: () => `/reports/employee-billing-history`,
    }
  ];

  const pipelineSteps = ['Select Invoice', 'Run Rule Engine', 'Post to Ledger', 'Done'];

  return (
    <Box className="fade-in-section">

      {/* ── Top: Invoice Selector ─────────────────────────────────────────── */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, md: 4 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
                <Box sx={{ p: 1, borderRadius: 1.5, background: 'rgba(6,182,212,0.12)', color: 'hsl(190,90%,50%)' }}>
                  <Activity size={20} />
                </Box>
                <Typography variant="h6" sx={{ fontWeight: 700 }}>Invoice Scope</Typography>
              </Box>

              {loadingInvoices ? (
                <CircularProgress size={20} />
              ) : invoices.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No invoices found. Upload an invoice workbook first.
                </Typography>
              ) : (
                <TextField
                  select
                  fullWidth
                  label="Select Invoice to Reconcile"
                  value={selectedInvoice}
                  onChange={e => { setSelectedInvoice(e.target.value); setStatusMsg(null); }}
                  size="small"
                >
                  {invoices.map(inv => (
                    <MenuItem key={inv.invoice_number} value={inv.invoice_number}>
                      {inv.invoice_number}&nbsp;
                      <Typography component="span" variant="caption" sx={{ color: 'text.secondary' }}>
                        ({inv.ledger_status || inv.status})
                      </Typography>
                    </MenuItem>
                  ))}
                </TextField>
              )}

              {summary && (
                <Box sx={{ mt: 2.5 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                    <Typography variant="caption" color="text.secondary">Invoice Status</Typography>
                    <StatusBadge status={summary.overall_status} />
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                    <Typography variant="caption" color="text.secondary">Invoice Date</Typography>
                    <Typography variant="caption" sx={{ fontWeight: 600 }}>{summary.invoice_date}</Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Typography variant="caption" color="text.secondary">Total Rows</Typography>
                    <Typography variant="caption" sx={{ fontWeight: 600 }}>{summary.total_rows}</Typography>
                  </Box>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* ── Pipeline Execution Panel ─────────────────────────────────────── */}
        <Grid size={{ xs: 12, md: 8 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
                <Box sx={{ p: 1, borderRadius: 1.5, background: 'rgba(99,102,241,0.12)', color: '#818cf8' }}>
                  <Zap size={20} />
                </Box>
                <Typography variant="h6" sx={{ fontWeight: 700 }}>Reconciliation Pipeline</Typography>
              </Box>

              <Typography variant="body2" color="text.secondary" sx={{ mb: 2.5 }}>
                Runs the full automated pipeline: <b>Validate</b> all rows against Employee Master, Separation History and Payment Ledger → <b>Auto-approve</b> if no FRAUD or ERROR violations exist → <b>Return</b> live Finance Summary.
              </Typography>

              {/* Stepper */}
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0, mb: 2.5 }}>
                {pipelineSteps.map((step, i) => {
                  const done = pipelineStep > i;
                  const active = pipelineStep === i + 1 && runningPipeline;
                  return (
                    <React.Fragment key={step}>
                      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 70 }}>
                        <Box sx={{
                          width: 28, height: 28, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                          background: done ? 'linear-gradient(135deg,#10b981,#059669)' : active ? 'linear-gradient(135deg,#6366f1,#818cf8)' : 'rgba(255,255,255,0.06)',
                          border: active ? '2px solid #818cf8' : 'none',
                          transition: 'all 0.4s',
                          boxShadow: active ? '0 0 12px rgba(99,102,241,0.5)' : 'none',
                          fontSize: '0.75rem', fontWeight: 800, color: '#fff'
                        }}>
                          {done ? <CheckCircle2 size={14} /> : active ? <CircularProgress size={14} sx={{ color: '#fff' }} /> : i + 1}
                        </Box>
                        <Typography variant="caption" sx={{ mt: 0.5, fontSize: '0.6rem', color: done || active ? 'text.primary' : 'text.secondary', textAlign: 'center', fontWeight: done || active ? 700 : 400 }}>
                          {step}
                        </Typography>
                      </Box>
                      {i < pipelineSteps.length - 1 && (
                        <Box sx={{ flexGrow: 1, height: 2, background: pipelineStep > i ? 'linear-gradient(90deg,#10b981,#6366f1)' : 'rgba(255,255,255,0.06)', mx: 0.5, borderRadius: 1, transition: 'background 0.4s', mb: 2.5 }} />
                      )}
                    </React.Fragment>
                  );
                })}
              </Box>

              {runningPipeline && (
                <LinearProgress sx={{ mb: 2, borderRadius: 1 }} />
              )}

              {statusMsg && (
                <Alert severity={statusMsg.type} sx={{ mb: 2, borderRadius: 2, fontSize: '0.82rem' }} onClose={() => setStatusMsg(null)}>
                  {statusMsg.text}
                </Alert>
              )}

              <Button
                fullWidth
                variant="contained"
                disabled={!selectedInvoice || runningPipeline || loadingSummary}
                onClick={handleRunReconciliation}
                startIcon={runningPipeline ? <CircularProgress size={18} sx={{ color: '#fff' }} /> : <Zap size={18} />}
                sx={{
                  py: 1.4,
                  background: 'linear-gradient(135deg, #6366f1 0%, #06b6d4 100%)',
                  '&:hover': { background: 'linear-gradient(135deg, #4f46e5 0%, #0891b2 100%)', transform: 'translateY(-1px)', boxShadow: '0 8px 24px rgba(99,102,241,0.35)' },
                  '&:disabled': { opacity: 0.5 },
                  transition: 'all 0.2s',
                  fontWeight: 700,
                  letterSpacing: '0.04em',
                }}
              >
                {runningPipeline ? 'Running Reconciliation Pipeline…' : 'Run Full Reconciliation'}
              </Button>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* ── Tabs Navigation ────────────────────────────────────────────────── */}
      <Tabs
        value={currentTab}
        onChange={(_, val) => setCurrentTab(val)}
        sx={{
          mb: 3,
          '& .MuiTabs-indicator': { background: 'linear-gradient(90deg, #6366f1, #06b6d4)' },
          '& .MuiTab-root': { fontWeight: 700, color: 'text.secondary' },
          '& .MuiTab-root.Mui-selected': { color: '#6366f1' }
        }}
      >
        <Tab label="Invoice Overview" />
        <Tab label="Ledger History" />
        <Tab label="Invoice Comparison" />
      </Tabs>

      {/* ── Tab 0: Invoice Overview ────────────────────────────────────────── */}
      {currentTab === 0 && (
        <>
          {(summary || loadingSummary) && (
            <>
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                <TrendingUp size={18} style={{ color: '#10b981' }} />
                Finance Summary — {selectedInvoice}
              </Typography>

              {loadingSummary ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 5 }}>
                  <CircularProgress />
                </Box>
              ) : summary ? (
                <>
                  <Grid container spacing={2} sx={{ mb: 2 }}>
                    <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                      <KpiCard label="Billed Total" value={fmt(summary.billed_total)} sub={`${summary.total_rows} rows`} icon={<IndianRupee size={16} />} accentColor="#94a3b8" glowColor="148,163,184" />
                    </Grid>
                    <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                      <KpiCard label="Approved" value={fmt(summary.approved_total)} sub={`${summary.approved_count} trainees`} icon={<CheckCircle2 size={16} />} accentColor="#10b981" glowColor="16,185,129" />
                    </Grid>
                    <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                      <KpiCard label="Rejected" value={fmt(summary.rejected_total)} sub={`${summary.rejected_count} trainees`} icon={<XCircle size={16} />} accentColor="#ef4444" glowColor="239,68,68" />
                    </Grid>
                    <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                      <KpiCard label="Pending" value={fmt(summary.pending_total)} sub={`${summary.pending_count} rows`} icon={<Clock size={16} />} accentColor="#f59e0b" glowColor="245,158,11" />
                    </Grid>
                    <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                      <KpiCard label="Money Saved" value={fmt(summary.money_saved)} sub="Fraud prevention" icon={<TrendingUp size={16} />} accentColor="#06b6d4" glowColor="6,182,212" />
                    </Grid>
                    <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                      <KpiCard label="Exceptions" value={`${summary.exception_count}`} sub={`${summary.fraud_count} fraud / ${summary.error_count} err`} icon={<AlertTriangle size={16} />} accentColor="#f97316" glowColor="249,115,22" />
                    </Grid>
                  </Grid>

                  {summary.billed_total > 0 && (
                    <Card sx={{ mb: 3, background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
                      <CardContent sx={{ py: 2 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                          <Typography variant="caption" color="text.secondary">Approval Rate</Typography>
                          <Typography variant="caption" sx={{ fontWeight: 700, color: '#10b981' }}>
                            {((summary.approved_total / summary.billed_total) * 100).toFixed(1)}%
                          </Typography>
                        </Box>
                        <LinearProgress
                          variant="determinate"
                          value={Math.min(100, (summary.approved_total / summary.billed_total) * 100)}
                          sx={{
                            height: 8, borderRadius: 4,
                            '& .MuiLinearProgress-bar': { background: 'linear-gradient(90deg, #10b981, #06b6d4)' },
                            backgroundColor: 'rgba(255,255,255,0.06)',
                          }}
                        />
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
                          <Typography variant="caption" color="text.secondary">
                            Fraud: <b style={{ color: '#ef4444' }}>{summary.fraud_count}</b>&nbsp;·&nbsp;
                            Errors: <b style={{ color: '#f59e0b' }}>{summary.error_count}</b>&nbsp;·&nbsp;
                            Warnings: <b style={{ color: '#94a3b8' }}>{summary.warning_count}</b>
                          </Typography>
                          <StatusBadge status={summary.overall_status} />
                        </Box>
                      </CardContent>
                    </Card>
                  )}
                </>
              ) : null}
            </>
          )}

          <Divider sx={{ mb: 3, borderColor: 'rgba(255,255,255,0.06)' }} />
          <Typography variant="h6" sx={{ fontWeight: 700, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
            <FileSpreadsheet size={18} style={{ color: '#818cf8' }} />
            Download Reports
          </Typography>

          <Grid container spacing={2}>
            {reports.map(rep => (
              <Grid key={rep.label} size={{ xs: 12, sm: 6, md: 4 }}>
                <Card
                  sx={{
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    border: `1px solid rgba(${rep.accentRgb},0.15)`,
                    background: `rgba(${rep.accentRgb},0.04)`,
                    transition: 'all 0.2s',
                    '&:hover': {
                      border: `1px solid rgba(${rep.accentRgb},0.35)`,
                      transform: 'translateY(-2px)',
                      boxShadow: `0 6px 20px rgba(${rep.accentRgb},0.12)`,
                    },
                  }}
                >
                  <CardContent sx={{ pb: 1 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.5 }}>
                      <Box sx={{ p: 1, borderRadius: 1.5, background: `rgba(${rep.accentRgb},0.12)`, color: `rgb(${rep.accentRgb})` }}>
                        {rep.icon}
                      </Box>
                      <Typography variant="subtitle2" sx={{ fontWeight: 700, fontSize: '0.875rem' }}>
                        {rep.label}
                      </Typography>
                    </Box>
                    <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1.5 }}>
                      {rep.desc}
                    </Typography>
                  </CardContent>
                  <Box sx={{ p: 2, pt: 0 }}>
                    <Tooltip title={!rep.global && !selectedInvoice ? 'Select an invoice first' : ''} placement="top">
                      <span>
                        <Button
                          fullWidth
                          variant="outlined"
                          size="small"
                          disabled={!rep.global && !selectedInvoice}
                          startIcon={<FileText size={14} />}
                          onClick={() => handleDownload(rep.endpoint())}
                          sx={{
                            borderColor: `rgba(${rep.accentRgb},0.3)`,
                            color: `rgb(${rep.accentRgb})`,
                            '&:hover': { borderColor: `rgb(${rep.accentRgb})`, background: `rgba(${rep.accentRgb},0.06)` },
                            fontWeight: 600,
                            fontSize: '0.75rem',
                          }}
                        >
                          Download Excel
                        </Button>
                      </span>
                    </Tooltip>
                  </Box>
                </Card>
              </Grid>
            ))}
          </Grid>
        </>
      )}

      {/* ── Tab 1: Global Ledger History ──────────────────────────────────── */}
      {currentTab === 1 && (
        <Card sx={{ background: 'rgba(255,255,255,0.01)', border: '1px solid rgba(255,255,255,0.06)' }}>
          <CardContent>
            <Typography variant="h6" sx={{ fontWeight: 700, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
              <History size={18} color="#6366f1" /> Global Invoice Ledger
            </Typography>
            <TableContainer component={Paper} sx={{ background: 'rgba(255,255,255,0.01)', border: '1px solid rgba(255,255,255,0.06)', boxShadow: 'none' }}>
              <Table size="small">
                <TableHead sx={{ backgroundColor: 'rgba(255,255,255,0.03)' }}>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 700, color: 'text.secondary' }}>Invoice Number</TableCell>
                    <TableCell sx={{ fontWeight: 700, color: 'text.secondary' }}>Date</TableCell>
                    <TableCell sx={{ fontWeight: 700, color: 'text.secondary' }}>Billing Month</TableCell>
                    <TableCell sx={{ fontWeight: 700, color: 'text.secondary' }}>Vendor</TableCell>
                    <TableCell sx={{ fontWeight: 700, color: 'text.secondary' }}>Billed (₹)</TableCell>
                    <TableCell sx={{ fontWeight: 700, color: 'text.secondary' }}>Approved (₹)</TableCell>
                    <TableCell sx={{ fontWeight: 700, color: 'text.secondary' }}>Rejected (₹)</TableCell>
                    <TableCell sx={{ fontWeight: 700, color: 'text.secondary' }}>Fraud (₹)</TableCell>
                    <TableCell sx={{ fontWeight: 700, color: 'text.secondary' }}>Rows</TableCell>
                    <TableCell sx={{ fontWeight: 700, color: 'text.secondary' }}>Ledger Status</TableCell>
                    <TableCell sx={{ fontWeight: 700, color: 'text.secondary' }}>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {invoices.map((inv) => (
                    <TableRow key={inv.invoice_number} hover sx={{ '&:last-child cell': { border: 0 } }}>
                      <TableCell sx={{ fontWeight: 600, color: '#fff' }}>{inv.invoice_number}</TableCell>
                      <TableCell>{inv.invoice_date}</TableCell>
                      <TableCell>{inv.billing_month} {inv.billing_year}</TableCell>
                      <TableCell>{inv.vendor_name || 'Tata Projects'}</TableCell>
                      <TableCell>{fmt(inv.billed_amount)}</TableCell>
                      <TableCell sx={{ color: 'success.main', fontWeight: 600 }}>{fmt(inv.approved_amount)}</TableCell>
                      <TableCell sx={{ color: 'error.main' }}>{fmt(inv.rejected_amount || 0)}</TableCell>
                      <TableCell sx={{ color: '#ef4444', fontWeight: 700 }}>{fmt(inv.fraud_amount || 0)}</TableCell>
                      <TableCell>{inv.record_count}</TableCell>
                      <TableCell>
                        <Chip
                          label={inv.ledger_status}
                          size="small"
                          color={inv.ledger_status === 'ACTIVE' ? 'success' : inv.ledger_status === 'SUPERSEDED' ? 'warning' : 'default'}
                          sx={{ fontWeight: 700, fontSize: '0.65rem', height: 20 }}
                        />
                      </TableCell>
                      <TableCell>
                        <Button
                          size="small"
                          variant="outlined"
                          onClick={() => { setSelectedInvoice(inv.invoice_number); setCurrentTab(0); }}
                          sx={{ fontSize: '0.7rem', py: 0.2 }}
                        >
                          Select
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                  {invoices.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={11} align="center" sx={{ py: 3, color: 'text.secondary' }}>
                        No invoice records available in history.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      )}

      {/* ── Tab 2: Invoice Comparison ────────────────────────────────────── */}
      {currentTab === 2 && (
        <Grid container spacing={3}>
          <Grid size={{ xs: 12, md: 4 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" sx={{ fontWeight: 700, mb: 2 }}>Compare Invoices</Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
                  <TextField
                    select
                    fullWidth
                    label="Base Invoice (A)"
                    value={compareA}
                    onChange={e => setCompareA(e.target.value)}
                    size="small"
                  >
                    {invoices.map(inv => (
                      <MenuItem key={inv.invoice_number} value={inv.invoice_number}>
                        {inv.invoice_number} ({inv.billing_month} {inv.billing_year})
                      </MenuItem>
                    ))}
                  </TextField>

                  <TextField
                    select
                    fullWidth
                    label="Compare Invoice (B)"
                    value={compareB}
                    onChange={e => setCompareB(e.target.value)}
                    size="small"
                  >
                    {invoices.map(inv => (
                      <MenuItem key={inv.invoice_number} value={inv.invoice_number}>
                        {inv.invoice_number} ({inv.billing_month} {inv.billing_year})
                      </MenuItem>
                    ))}
                  </TextField>

                  {compareError && <Alert severity="error">{compareError}</Alert>}

                  <Button
                    variant="contained"
                    disabled={!compareA || !compareB || comparing}
                    onClick={handleCompare}
                    sx={{
                      background: 'linear-gradient(135deg, #6366f1 0%, #06b6d4 100%)',
                      fontWeight: 700
                    }}
                  >
                    {comparing ? <CircularProgress size={20} /> : 'Compare Invoices'}
                  </Button>
                  
                  {comparisonResult && (
                    <Button
                      variant="outlined"
                      color="secondary"
                      onClick={() => handleDownload(`/reports/invoice-comparison/${compareA}/${compareB}`)}
                      startIcon={<FileText size={16} />}
                      sx={{ fontWeight: 600 }}
                    >
                      Export Comparison Excel
                    </Button>
                  )}
                </Box>
              </CardContent>
            </Card>
          </Grid>
          
          <Grid size={{ xs: 12, md: 8 }}>
            {comparisonResult ? (
              <Card sx={{ background: 'rgba(255,255,255,0.01)', border: '1px solid rgba(255,255,255,0.06)' }}>
                <CardContent>
                  <Typography variant="h6" sx={{ fontWeight: 700, mb: 3 }}>
                    Comparison: {compareA} vs {compareB}
                  </Typography>
                  
                  <Grid container spacing={2} sx={{ mb: 4 }}>
                    <Grid size={{ xs: 6, sm: 3 }}>
                      <Box sx={{ p: 2, borderRadius: 2, background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
                        <Typography variant="caption" color="text.secondary">INVOICE A TOTAL</Typography>
                        <Typography variant="h6" sx={{ fontWeight: 800 }}>{fmt(comparisonResult.invoice_a_total)}</Typography>
                      </Box>
                    </Grid>
                    <Grid size={{ xs: 6, sm: 3 }}>
                      <Box sx={{ p: 2, borderRadius: 2, background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
                        <Typography variant="caption" color="text.secondary">INVOICE B TOTAL</Typography>
                        <Typography variant="h6" sx={{ fontWeight: 800 }}>{fmt(comparisonResult.invoice_b_total)}</Typography>
                      </Box>
                    </Grid>
                    <Grid size={{ xs: 6, sm: 3 }}>
                      <Box sx={{ p: 2, borderRadius: 2, background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
                        <Typography variant="caption" color="text.secondary">NET DIFFERENCE</Typography>
                        <Typography variant="h6" sx={{ fontWeight: 800, color: (comparisonResult.invoice_b_total - comparisonResult.invoice_a_total) >= 0 ? 'success.main' : 'error.main' }}>
                          {fmt(comparisonResult.invoice_b_total - comparisonResult.invoice_a_total)}
                        </Typography>
                      </Box>
                    </Grid>
                    <Grid size={{ xs: 6, sm: 3 }}>
                      <Box sx={{ p: 2, borderRadius: 2, background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
                        <Typography variant="caption" color="text.secondary">COMMON EMPLOYEES</Typography>
                        <Typography variant="h6" sx={{ fontWeight: 800 }}>{comparisonResult.common_count}</Typography>
                      </Box>
                    </Grid>
                  </Grid>

                  <Divider sx={{ my: 3, borderColor: 'rgba(255,255,255,0.06)' }} />

                  {/* Added Employees */}
                  <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'success.main', mb: 1.5 }}>
                    Added Employees ({comparisonResult.added_employees.length})
                  </Typography>
                  <Box sx={{ maxHeight: 200, overflowY: 'auto', mb: 4, border: '1px solid rgba(255,255,255,0.04)', borderRadius: 2, p: 1.5, background: 'rgba(255,255,255,0.005)' }}>
                    {comparisonResult.added_employees.map((emp: any, i: number) => (
                      <Typography key={i} variant="body2" color="text.secondary" sx={{ py: 0.5, borderBottom: '1px solid rgba(255,255,255,0.02)' }}>
                        <b>{emp.trainee_id || emp.ticket_number}</b> - {emp.name || 'Unknown'} (Billed: {fmt(emp.billed_total)})
                      </Typography>
                    ))}
                    {comparisonResult.added_employees.length === 0 && (
                      <Typography variant="body2" color="text.secondary">No added employees.</Typography>
                    )}
                  </Box>

                  {/* Removed Employees */}
                  <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'error.main', mb: 1.5 }}>
                    Removed Employees ({comparisonResult.removed_employees.length})
                  </Typography>
                  <Box sx={{ maxHeight: 200, overflowY: 'auto', mb: 4, border: '1px solid rgba(255,255,255,0.04)', borderRadius: 2, p: 1.5, background: 'rgba(255,255,255,0.005)' }}>
                    {comparisonResult.removed_employees.map((emp: any, i: number) => (
                      <Typography key={i} variant="body2" color="text.secondary" sx={{ py: 0.5, borderBottom: '1px solid rgba(255,255,255,0.02)' }}>
                        <b>{emp.trainee_id || emp.ticket_number}</b> - {emp.name || 'Unknown'} (Billed: {fmt(emp.billed_total)})
                      </Typography>
                    ))}
                    {comparisonResult.removed_employees.length === 0 && (
                      <Typography variant="body2" color="text.secondary">No removed employees.</Typography>
                    )}
                  </Box>

                  {/* Changed Payouts */}
                  <Typography variant="subtitle2" sx={{ fontWeight: 700, color: '#f59e0b', mb: 1.5 }}>
                    Changed Payouts ({comparisonResult.changed_employees.length})
                  </Typography>
                  <Box sx={{ maxHeight: 200, overflowY: 'auto', border: '1px solid rgba(255,255,255,0.04)', borderRadius: 2, p: 1.5, background: 'rgba(255,255,255,0.005)' }}>
                    {comparisonResult.changed_employees.map((emp: any, i: number) => (
                      <Typography key={i} variant="body2" color="text.secondary" sx={{ py: 0.5, borderBottom: '1px solid rgba(255,255,255,0.02)' }}>
                        <b>{emp.trainee_id || emp.ticket_number}</b> - {emp.name || 'Unknown'} (Billed A: {fmt(emp.a_billed)} → Billed B: {fmt(emp.b_billed)}, Diff: {fmt(emp.diff)})
                      </Typography>
                    ))}
                    {comparisonResult.changed_employees.length === 0 && (
                      <Typography variant="body2" color="text.secondary">No changed payouts.</Typography>
                    )}
                  </Box>
                </CardContent>
              </Card>
            ) : (
              <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: 300, border: '2px dashed rgba(255,255,255,0.06)', borderRadius: 3, p: 4, background: 'rgba(255,255,255,0.002)' }}>
                <FileSpreadsheet size={48} color="rgba(255,255,255,0.2)" />
                <Typography variant="subtitle1" sx={{ mt: 2, fontWeight: 700, color: 'text.secondary' }}>
                  No comparison loaded
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', maxWidth: 300, mt: 0.5 }}>
                  Select a base and target invoice, then click "Compare Invoices" to analyze differences.
                </Typography>
              </Box>
            )}
          </Grid>
        </Grid>
      )}
    </Box>
  );
};
