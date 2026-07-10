import React, { useEffect, useState } from 'react';
import { 
  Box, 
  Grid, 
  Card, 
  CardContent, 
  Typography, 
  Button, 
  Chip, 
  CircularProgress,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  TextField,
  InputAdornment,
  IconButton,
  Tooltip
} from '@mui/material';
import { 
  Users, 
  ShieldAlert, 
  Coins, 
  FileSpreadsheet, 
  ArrowRight,
  TrendingUp,
  AlertTriangle,
  UserMinus,
  Ban,
  Settings as SettingsIcon,
  Search,
  X,
  Shirt,
  Calendar,
  IndianRupee,
  ShieldCheck,
  CheckCircle2,
  Inbox
} from 'lucide-react';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  Tooltip as ChartTooltip, 
  ResponsiveContainer,
  PieChart, 
  Pie, 
  Cell, 
  Legend,
  LineChart,
  Line,
  AreaChart,
  Area
} from 'recharts';
import api from '../api';

interface DashboardStats {
  total_trainees: number;
  active_trainees: number;
  blocked_trainees: number;
  separated_trainees: number;
  naps_count: number;
  btech_count: number;
  mtech_count: number;
  joining_this_month: number;
  separations_this_month: number;
  early_separations: number;
  pending_invoices_count: number;
  pending_invoices_amount: number;
  total_billed_amount: number;
  total_approved_amount: number;
  total_rejected_amount: number;
  savings_generated: number;
  total_payments: number;
  total_shirts: number;
  total_jeans: number;
  exception_count: number;
  fraud_count: number;
  recent_alerts: any[];
  chart_billing: any[];
  chart_joining: any[];
  chart_separation: any[];
  chart_categories: any[];
  chart_fraud: any[];
  chart_payments: any[];
}

interface DashboardProps {
  onPageChange: (page: string) => void;
}

interface DrillDownState {
  open: boolean;
  title: string;
  type: 'trainee' | 'invoice' | 'fraud' | 'ledger';
  endpoint: string;
  data: any[];
  loading: boolean;
}

interface KpiCardProps {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ReactNode;
  accentColor: string;
  glowColor: string;
  onClick?: () => void;
}

const KpiCard: React.FC<KpiCardProps> = ({ label, value, sub, icon, accentColor, glowColor, onClick }) => (
  <Card
    onClick={onClick}
    sx={{
      cursor: onClick ? 'pointer' : 'default',
      background: `linear-gradient(135deg, rgba(${glowColor},0.06) 0%, rgba(0,0,0,0) 70%)`,
      border: `1px solid rgba(${glowColor},0.15)`,
      boxShadow: `0 0 20px rgba(${glowColor},0.03)`,
      transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
      '&:hover': { 
        transform: onClick ? 'translateY(-2px)' : 'none', 
        boxShadow: onClick ? `0 6px 24px rgba(${glowColor},0.12)` : `0 0 20px rgba(${glowColor},0.03)`,
        border: onClick ? `1px solid rgba(${glowColor},0.35)` : `1px solid rgba(${glowColor},0.15)`,
      },
    }}
  >
    <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
        <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', fontSize: '0.65rem' }}>
          {label}
        </Typography>
        <Box sx={{ p: 0.6, borderRadius: 1.2, background: `rgba(${glowColor},0.1)`, color: accentColor }}>
          {icon}
        </Box>
      </Box>
      <Typography variant="h5" sx={{ fontWeight: 800, color: '#fff', lineHeight: 1.2 }}>
        {value}
      </Typography>
      {sub && (
        <Typography variant="caption" sx={{ color: 'text.secondary', mt: 0.5, display: 'block', fontSize: '0.7rem' }}>
          {sub}
        </Typography>
      )}
    </CardContent>
  </Card>
);

export const Dashboard: React.FC<DashboardProps> = ({ onPageChange }) => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Drill down state
  const [drillDown, setDrillDown] = useState<DrillDownState>({
    open: false,
    title: '',
    type: 'trainee',
    endpoint: '',
    data: [],
    loading: false
  });
  const [searchTerm, setSearchTerm] = useState('');

  const fetchStats = async () => {
    try {
      setLoading(true);
      const res = await api.get('/dashboard/stats');
      setStats(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch dashboard metrics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  const handleCardClick = async (title: string, type: 'trainee' | 'invoice' | 'fraud' | 'ledger', endpoint: string) => {
    setDrillDown({
      open: true,
      title,
      type,
      endpoint,
      data: [],
      loading: true
    });
    setSearchTerm('');
    try {
      const res = await api.get(endpoint);
      setDrillDown(prev => ({
        ...prev,
        data: res.data,
        loading: false
      }));
    } catch (err) {
      setDrillDown(prev => ({
        ...prev,
        loading: false
      }));
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
        <CircularProgress color="secondary" />
      </Box>
    );
  }

  if (error || !stats) {
    return (
      <Box sx={{ p: 3, textAlign: 'center', color: 'error.main' }}>
        <Typography variant="h6">{error || 'Data could not be loaded'}</Typography>
        <Button onClick={fetchStats} variant="outlined" sx={{ mt: 2 }}>Retry</Button>
      </Box>
    );
  }

  // Colors for charts
  const PIE_COLORS = ['#10b981', '#f59e0b', '#ef4444'];
  const CATEGORY_COLORS = ['#6366f1', '#06b6d4', '#8b5cf6'];

  const statusPieData = [
    { name: 'Active', value: stats.active_trainees },
    { name: 'Separated', value: stats.separated_trainees },
    { name: 'Blocked', value: stats.blocked_trainees }
  ].filter(d => d.value > 0);

  // Combine monthly joining and separations into a single series for trend visualization
  const joinMap = new Map(stats.chart_joining?.map((j: any) => [j.month, j.count]) || []);
  const sepMap = new Map(stats.chart_separation?.map((s: any) => [s.month, s.count]) || []);
  const allMonths = Array.from(new Set([
    ...(stats.chart_joining?.map((j: any) => j.month) || []),
    ...(stats.chart_separation?.map((s: any) => s.month) || [])
  ])).sort();

  const joiningSeparationTrend = allMonths.map(m => ({
    month: m,
    Joining: joinMap.get(m) || 0,
    Separation: sepMap.get(m) || 0
  })).slice(-12); // Limit to last 12 months for clarity

  // Format currency
  const fmt = (v: number) => `₹${(v ?? 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

  // Filter drill down data locally
  const filteredData = drillDown.data.filter((item: any) => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    
    if (drillDown.type === 'trainee') {
      return (
        item.id?.toLowerCase().includes(term) ||
        item.name?.toLowerCase().includes(term) ||
        item.scheme?.toLowerCase().includes(term) ||
        item.status?.toLowerCase().includes(term)
      );
    } else if (drillDown.type === 'invoice') {
      return (
        item.invoice_number?.toLowerCase().includes(term) ||
        item.status?.toLowerCase().includes(term)
      );
    } else if (drillDown.type === 'fraud') {
      return (
        item.trainee_id?.toLowerCase().includes(term) ||
        item.invoice_number?.toLowerCase().includes(term) ||
        item.rule_name?.toLowerCase().includes(term) ||
        item.message?.toLowerCase().includes(term)
      );
    } else if (drillDown.type === 'ledger') {
      return (
        item.trainee_id?.toLowerCase().includes(term) ||
        item.trainee_name?.toLowerCase().includes(term) ||
        item.invoice_number?.toLowerCase().includes(term) ||
        item.payment_type?.toLowerCase().includes(term)
      );
    }
    return true;
  });

  return (
    <Box className="fade-in-section">
      {/* Top Header & Actions */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 800 }}>Welcome Back, Admin</Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>Real-time compliance monitoring, payment ledger controls, and trainee lifecycle logs.</Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button 
            variant="contained" 
            color="primary" 
            startIcon={<FileSpreadsheet size={16} />}
            onClick={() => onPageChange('upload_invoice')}
            sx={{
              background: 'linear-gradient(135deg, #6366f1 0%, #06b6d4 100%)',
              '&:hover': { background: 'linear-gradient(135deg, #4f46e5 0%, #0891b2 100%)', transform: 'translateY(-1px)' },
              fontWeight: 700
            }}
          >
            Audit New Invoice
          </Button>
        </Box>
      </Box>

      {/* ── SECTION 1: TRAINEE LIFECYCLE STATS (10 KPIs) ───────────────────── */}
      <Typography variant="subtitle2" sx={{ color: 'primary.main', fontWeight: 800, mb: 1.5, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
        Trainee Master & Lifecycle Metrics
      </Typography>
      <Grid container spacing={2} sx={{ mb: 4 }}>
        <Grid size={{ xs: 6, sm: 4, md: 2.4 }}>
          <KpiCard 
            label="Total Trainees" 
            value={stats.total_trainees} 
            sub="Ingested in master"
            icon={<Users size={16} />} 
            accentColor="#94a3b8" 
            glowColor="148,163,184"
            onClick={() => handleCardClick("Total Ingested Trainees", "trainee", "/trainees")}
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2.4 }}>
          <KpiCard 
            label="Active Trainees" 
            value={stats.active_trainees} 
            sub="Currently verified active"
            icon={<CheckCircle2 size={16} />} 
            accentColor="#10b981" 
            glowColor="16,185,129"
            onClick={() => handleCardClick("Active Trainees", "trainee", "/trainees?status=ACTIVE")}
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2.4 }}>
          <KpiCard 
            label="Separated Employees" 
            value={stats.separated_trainees} 
            sub="Trainees left (compliant)"
            icon={<UserMinus size={16} />} 
            accentColor="#f59e0b" 
            glowColor="245,158,11"
            onClick={() => handleCardClick("Separated Trainees", "trainee", "/trainees?status=SEPARATED")}
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2.4 }}>
          <KpiCard 
            label="Blocked Trainees" 
            value={stats.blocked_trainees} 
            sub="Permanently blocked"
            icon={<Ban size={16} />} 
            accentColor="#ef4444" 
            glowColor="239,68,68"
            onClick={() => handleCardClick("Blocked Trainees", "trainee", "/trainees?status=BLOCKED")}
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2.4 }}>
          <KpiCard 
            label="Joining This Month" 
            value={stats.joining_this_month} 
            sub="Ingested DOJs"
            icon={<Calendar size={16} />} 
            accentColor="#818cf8" 
            glowColor="99,102,241"
            onClick={() => handleCardClick("Joined This Month", "trainee", "/trainees?joining_this_month=true")}
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2.4 }}>
          <KpiCard 
            label="Separations Month" 
            value={stats.separations_this_month} 
            sub="Ingested DOLs"
            icon={<UserMinus size={16} />} 
            accentColor="#f97316" 
            glowColor="249,115,22"
            onClick={() => handleCardClick("Separations This Month", "trainee", "/trainees?separations_this_month=true")}
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2.4 }}>
          <KpiCard 
            label="Early Separations" 
            value={stats.early_separations} 
            sub="Resigned < 30 days"
            icon={<AlertTriangle size={16} />} 
            accentColor="#f43f5e" 
            glowColor="244,63,94"
            onClick={() => handleCardClick("Early Separations (< 30 days)", "trainee", "/trainees?early_separations=true")}
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2.4 }}>
          <KpiCard 
            label="NAPS Trainees" 
            value={stats.naps_count} 
            sub="NAPS scheme quota"
            icon={<Users size={16} />} 
            accentColor="#3b82f6" 
            glowColor="59,130,246"
            onClick={() => handleCardClick("NAPS Trainees", "trainee", "/trainees?scheme=NAPS")}
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2.4 }}>
          <KpiCard 
            label="B.Tech Trainees" 
            value={stats.btech_count} 
            sub="B.Tech scheme quota"
            icon={<Users size={16} />} 
            accentColor="#06b6d4" 
            glowColor="6,182,212"
            onClick={() => handleCardClick("B.Tech Trainees", "trainee", "/trainees?scheme=B.Tech")}
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2.4 }}>
          <KpiCard 
            label="M.Tech Trainees" 
            value={stats.mtech_count} 
            sub="M.Tech scheme quota"
            icon={<Users size={16} />} 
            accentColor="#8b5cf6" 
            glowColor="139,92,246"
            onClick={() => handleCardClick("M.Tech Trainees", "trainee", "/trainees?scheme=M.Tech")}
          />
        </Grid>
      </Grid>

      {/* ── SECTION 2: FINANCIAL RECONCILIATION & AUDIT (7 KPIs) ───────────── */}
      <Typography variant="subtitle2" sx={{ color: 'secondary.main', fontWeight: 800, mb: 1.5, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
        Financial Auditing & Payout reconciliation
      </Typography>
      <Grid container spacing={2} sx={{ mb: 4 }}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiCard 
            label="Total Claims Billed" 
            value={fmt(stats.total_billed_amount)} 
            sub="Total vendor claims"
            icon={<Coins size={16} />} 
            accentColor="#94a3b8" 
            glowColor="148,163,184"
            onClick={() => handleCardClick("All Invoices (Billed Claims)", "invoice", "/invoices")}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiCard 
            label="Approved Payouts" 
            value={fmt(stats.total_approved_amount)} 
            sub="Compliant payouts"
            icon={<ShieldCheck size={16} />} 
            accentColor="#10b981" 
            glowColor="16,185,129"
            onClick={() => handleCardClick("Approved Invoices", "invoice", "/invoices?status=APPROVED")}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiCard 
            label="Rejected Payouts" 
            value={fmt(stats.total_rejected_amount)} 
            sub="Non-compliant claims rejected"
            icon={<Ban size={16} />} 
            accentColor="#ef4444" 
            glowColor="239,68,68"
            onClick={() => handleCardClick("Audit Exceptions/Rejections", "invoice", "/invoices?status=EXCEPTION")}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiCard 
            label="Savings Generated" 
            value={fmt(stats.savings_generated)} 
            sub="Audited savings"
            icon={<TrendingUp size={16} />} 
            accentColor="#06b6d4" 
            glowColor="6,182,212"
            onClick={() => handleCardClick("Audit Saving Ledger (Invoices)", "invoice", "/invoices")}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiCard 
            label="Disbursed Payments (Ledger)" 
            value={fmt(stats.total_payments)} 
            sub="Total lifetime posted ledger disbursements"
            icon={<IndianRupee size={16} />} 
            accentColor="#6366f1" 
            glowColor="99,102,241"
            onClick={() => handleCardClick("Disbursed Payments Ledger", "ledger", "/ledger")}
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 3, md: 3 }}>
          <KpiCard 
            label="Pending Invoices" 
            value={stats.pending_invoices_count} 
            sub="Awaiting reconciliation run"
            icon={<Inbox size={16} />} 
            accentColor="#f59e0b" 
            glowColor="245,158,11"
            onClick={() => handleCardClick("Pending Invoices", "invoice", "/invoices?status=PENDING")}
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 3, md: 3 }}>
          <KpiCard 
            label="Pending Claims Value" 
            value={fmt(stats.pending_invoices_amount)} 
            sub="Awaiting review total value"
            icon={<Coins size={16} />} 
            accentColor="#f59e0b" 
            glowColor="245,158,11"
            onClick={() => handleCardClick("Pending Invoices Claims", "invoice", "/invoices?status=PENDING")}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiCard 
            label="Fraud Cases" 
            value={`${stats.fraud_count} Incidents`} 
            sub="Validation fraud flags"
            icon={<ShieldAlert size={16} />} 
            accentColor="#ef4444" 
            glowColor="239,68,68"
            onClick={() => handleCardClick("Fraud Cases & Incidents", "fraud", "/dashboard/fraud-alerts")}
          />
        </Grid>
      </Grid>

      {/* ── SECTION 3: APPROVED KIT ALLOCATIONS (2 KPIs) ───────────────────── */}
      <Typography variant="subtitle2" sx={{ color: 'success.main', fontWeight: 800, mb: 1.5, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
        Trainee Kit Audits
      </Typography>
      <Grid container spacing={2} sx={{ mb: 4 }}>
        <Grid size={{ xs: 12, sm: 6 }}>
          <KpiCard 
            label="Approved Shirts" 
            value={`${stats.total_shirts} Shirts`} 
            sub="Cumulative audited shirt quantity approved"
            icon={<Shirt size={16} />} 
            accentColor="#10b981" 
            glowColor="16,185,129"
            onClick={() => handleCardClick("Kit Audited Invoices (Approved)", "invoice", "/invoices?status=APPROVED")}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <KpiCard 
            label="Approved Jeans" 
            value={`${stats.total_jeans} Jeans`} 
            sub="Cumulative audited jeans quantity approved"
            icon={<Shirt size={16} />} 
            accentColor="#10b981" 
            glowColor="16,185,129"
            onClick={() => handleCardClick("Kit Audited Invoices (Approved)", "invoice", "/invoices?status=APPROVED")}
          />
        </Grid>
      </Grid>

      {/* Charts Grid */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        {/* Financial reconciliation graph */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Card>
            <CardContent>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 2 }}>Financial Reconciliation (Billed vs Approved)</Typography>
              <Box sx={{ height: 300, width: '100%' }}>
                {stats.chart_billing.length === 0 ? (
                  <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
                    <Typography variant="body2" sx={{ color: 'text.secondary' }}>No invoices uploaded yet</Typography>
                  </Box>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={stats.chart_billing} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
                      <XAxis dataKey="name" stroke="#6b7280" fontSize={11} tickLine={false} />
                      <YAxis stroke="#6b7280" fontSize={11} tickLine={false} />
                      <ChartTooltip 
                        contentStyle={{ background: '#111827', borderColor: 'rgba(255,255,255,0.08)', borderRadius: 8 }} 
                        labelStyle={{ fontWeight: 600 }}
                      />
                      <Legend verticalAlign="top" height={36} />
                      <Bar dataKey="billed" name="Billed Claims" fill="rgba(99, 102, 241, 0.4)" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="approved" name="Approved Payout" fill="#10b981" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Monthly Joining vs Monthly Separation */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 2 }}>Trainee Life Cycle Trends (Joining vs Separation)</Typography>
              <Box sx={{ height: 300, width: '100%' }}>
                {joiningSeparationTrend.length === 0 ? (
                  <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
                    <Typography variant="body2" sx={{ color: 'text.secondary' }}>No lifecycle logs found</Typography>
                  </Box>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={joiningSeparationTrend} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
                      <defs>
                        <linearGradient id="colorJoining" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#6366f1" stopOpacity={0.2}/>
                          <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                        </linearGradient>
                        <linearGradient id="colorSeparation" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.2}/>
                          <stop offset="95%" stopColor="#f59e0b" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <XAxis dataKey="month" stroke="#6b7280" fontSize={11} tickLine={false} />
                      <YAxis stroke="#6b7280" fontSize={11} tickLine={false} />
                      <ChartTooltip 
                        contentStyle={{ background: '#111827', borderColor: 'rgba(255,255,255,0.08)', borderRadius: 8 }} 
                      />
                      <Legend verticalAlign="top" height={36} />
                      <Area type="monotone" dataKey="Joining" name="Joined Trainees" stroke="#6366f1" fillOpacity={1} fill="url(#colorJoining)" strokeWidth={2} />
                      <Area type="monotone" dataKey="Separation" name="Separated Trainees" stroke="#f59e0b" fillOpacity={1} fill="url(#colorSeparation)" strokeWidth={2} />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Pie Charts row */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        {/* Status Distribution */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ pb: 1 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>Trainee Registry Status Ratio</Typography>
              <Box sx={{ height: 240, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                {statusPieData.length === 0 ? (
                  <Typography variant="body2" sx={{ color: 'text.secondary' }}>No trainees in database</Typography>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={statusPieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={50}
                        outerRadius={70}
                        paddingAngle={5}
                        dataKey="value"
                      >
                        {statusPieData.map((_, index) => (
                          <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                        ))}
                      </Pie>
                      <ChartTooltip contentStyle={{ background: '#111827', borderColor: 'rgba(255,255,255,0.08)', borderRadius: 8 }} />
                      <Legend verticalAlign="bottom" height={36} />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Scheme Distribution */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ pb: 1 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>Category / Scheme Distribution</Typography>
              <Box sx={{ height: 240, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                {stats.chart_categories.length === 0 ? (
                  <Typography variant="body2" sx={{ color: 'text.secondary' }}>No scheme metrics found</Typography>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={stats.chart_categories}
                        cx="50%"
                        cy="50%"
                        innerRadius={50}
                        outerRadius={70}
                        paddingAngle={5}
                        dataKey="value"
                      >
                        {stats.chart_categories.map((_, index) => (
                          <Cell key={`cell-${index}`} fill={CATEGORY_COLORS[index % CATEGORY_COLORS.length]} />
                        ))}
                      </Pie>
                      <ChartTooltip contentStyle={{ background: '#111827', borderColor: 'rgba(255,255,255,0.08)', borderRadius: 8 }} />
                      <Legend verticalAlign="bottom" height={36} />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Cumulative Payments Trend */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ pb: 1 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>Monthly Payments Trend</Typography>
              <Box sx={{ height: 240, width: '100%' }}>
                {stats.chart_payments.length === 0 ? (
                  <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
                    <Typography variant="body2" sx={{ color: 'text.secondary' }}>No ledger disbursements</Typography>
                  </Box>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={stats.chart_payments} margin={{ top: 10, right: 10, left: -20, bottom: 5 }}>
                      <defs>
                        <linearGradient id="colorPayments" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#10b981" stopOpacity={0.2}/>
                          <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <XAxis dataKey="month" stroke="#6b7280" fontSize={10} tickLine={false} />
                      <YAxis stroke="#6b7280" fontSize={10} tickLine={false} />
                      <ChartTooltip 
                        contentStyle={{ background: '#111827', borderColor: 'rgba(255,255,255,0.08)', borderRadius: 8 }} 
                        formatter={(value: any) => fmt(value)}
                      />
                      <Area type="monotone" dataKey="amount" name="Disbursed" stroke="#10b981" fillOpacity={1} fill="url(#colorPayments)" strokeWidth={2} />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Third row: Fraud Trend, Recent Alerts & Quick Links */}
      <Grid container spacing={3}>
        {/* Fraud Trend */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 2 }}>Fraud Incident Trend</Typography>
              <Box sx={{ height: 260, width: '100%' }}>
                {stats.chart_fraud.length === 0 ? (
                  <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
                    <Typography variant="body2" sx={{ color: 'text.secondary' }}>No fraud cases recorded. Secure environment.</Typography>
                  </Box>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={stats.chart_fraud} margin={{ top: 10, right: 10, left: -20, bottom: 5 }}>
                      <XAxis dataKey="month" stroke="#6b7280" fontSize={11} tickLine={false} />
                      <YAxis stroke="#6b7280" fontSize={11} tickLine={false} />
                      <ChartTooltip contentStyle={{ background: '#111827', borderColor: 'rgba(255,255,255,0.08)', borderRadius: 8 }} />
                      <Line type="monotone" dataKey="count" name="Incidents" stroke="#ef4444" strokeWidth={2} activeDot={{ r: 6 }} />
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Recent Security alerts list */}
        <Grid size={{ xs: 12, md: 5 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>Recent Audit Violations</Typography>
                <Button 
                  endIcon={<ArrowRight size={14} />} 
                  color="secondary"
                  onClick={() => onPageChange('validation')}
                  sx={{ fontSize: '0.8rem', fontWeight: 700 }}
                >
                  Validation Logs
                </Button>
              </Box>
              <Box sx={{ maxHeight: 260, overflowY: 'auto' }}>
                {stats.recent_alerts.length === 0 ? (
                  <Typography variant="body2" sx={{ color: 'text.secondary', p: 2, textAlign: 'center' }}>
                    No audit alerts triggered. System status: SECURE.
                  </Typography>
                ) : (
                  <List disablePadding>
                    {stats.recent_alerts.map((alert) => (
                      <ListItem 
                        key={alert.id} 
                        sx={{ 
                          borderBottom: '1px solid rgba(255,255,255,0.05)',
                          py: 1.2,
                          px: 1,
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: 1.5
                        }}
                      >
                        <ListItemIcon sx={{ minWidth: 'auto', mt: 0.5 }}>
                          {alert.status === 'FRAUD' ? (
                            <Ban size={18} color="#ef4444" />
                          ) : alert.status === 'ERROR' ? (
                            <AlertTriangle size={18} color="#f59e0b" />
                          ) : (
                            <AlertTriangle size={18} color="#3b82f6" />
                          )}
                        </ListItemIcon>
                        <ListItemText
                          primary={
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                              <Typography variant="body2" sx={{ fontWeight: 700 }}>
                                ID: {alert.trainee_id || 'N/A'} • Invoice: {alert.invoice_number}
                              </Typography>
                              <Chip 
                                label={alert.status} 
                                size="small" 
                                color={alert.status === 'FRAUD' ? 'error' : alert.status === 'ERROR' ? 'warning' : 'info'}
                                sx={{ height: 18, fontSize: '0.65rem', fontWeight: 800 }}
                              />
                            </Box>
                          }
                          secondary={
                            <Box>
                              <Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '0.82rem', lineHeight: 1.4 }}>
                                {alert.message}
                              </Typography>
                              <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.3)', display: 'block', mt: 0.5 }}>
                                Logged: {alert.created_at} • Rule: {alert.rule_name}
                              </Typography>
                            </Box>
                          }
                        />
                      </ListItem>
                    ))}
                  </List>
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Quick Links */}
        <Grid size={{ xs: 12, md: 3 }}>
          <Card sx={{ height: '100%', background: 'linear-gradient(135deg, rgba(17, 24, 39, 0.8) 0%, rgba(99, 102, 241, 0.04) 100%)' }}>
            <CardContent>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 2 }}>Data Ingestion Feeds</Typography>
              
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                {/* BDC Master link */}
                <Box 
                  onClick={() => onPageChange('upload_bdc')}
                  sx={{ 
                    p: 1.5, 
                    borderRadius: 2, 
                    border: '1px solid rgba(255,255,255,0.06)', 
                    background: 'rgba(255,255,255,0.01)',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    '&:hover': {
                      background: 'rgba(99,102,241,0.08)',
                      borderColor: 'rgba(99,102,241,0.3)',
                      transform: 'translateX(2px)'
                    }
                  }}
                >
                  <Typography variant="subtitle2" sx={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: 1, fontSize: '0.85rem' }}>
                    <Users size={15} color="#6366f1" /> Import BDC Master
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 0.3, fontSize: '0.72rem' }}>
                    Register new joins, schemes, and IDs.
                  </Typography>
                </Box>

                {/* Separation link */}
                <Box 
                  onClick={() => onPageChange('upload_separation')}
                  sx={{ 
                    p: 1.5, 
                    borderRadius: 2, 
                    border: '1px solid rgba(255,255,255,0.06)', 
                    background: 'rgba(255,255,255,0.01)',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    '&:hover': {
                      background: 'rgba(6, 182, 212, 0.08)',
                      borderColor: 'rgba(6, 182, 212, 0.3)',
                      transform: 'translateX(2px)'
                    }
                  }}
                >
                  <Typography variant="subtitle2" sx={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: 1, fontSize: '0.85rem' }}>
                    <UserMinus size={15} color="#06b6d4" /> Import Separation
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 0.3, fontSize: '0.72rem' }}>
                    Ingest Date of Leaving and resignations.
                  </Typography>
                </Box>

                {/* Settings link */}
                <Box 
                  onClick={() => onPageChange('settings')}
                  sx={{ 
                    p: 1.5, 
                    borderRadius: 2, 
                    border: '1px solid rgba(255,255,255,0.06)', 
                    background: 'rgba(255,255,255,0.01)',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    '&:hover': {
                      background: 'rgba(255,255,255,0.04)',
                      borderColor: 'rgba(255,255,255,0.15)',
                      transform: 'translateX(2px)'
                    }
                  }}
                >
                  <Typography variant="subtitle2" sx={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: 1, fontSize: '0.85rem' }}>
                    <SettingsIcon size={15} /> Configure Rules
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 0.3, fontSize: '0.72rem' }}>
                    Verify thresholds and policy parameters.
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* ── DRILL DOWN DETAILS DIALOG MODAL ───────────────────────────────── */}
      <Dialog 
        open={drillDown.open} 
        onClose={() => setDrillDown(prev => ({ ...prev, open: false }))}
        maxWidth="lg"
        fullWidth
        slotProps={{
          paper: {
            sx: {
              background: '#0d111d',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5)',
              backgroundImage: 'radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.08) 0px, transparent 50%)',
            }
          }
        }}
      >
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', pr: 2, pb: 1.5 }}>
          <Typography variant="h6" sx={{ fontWeight: 800 }}>
            {drillDown.title} ({drillDown.loading ? '...' : filteredData.length})
          </Typography>
          <IconButton onClick={() => setDrillDown(prev => ({ ...prev, open: false }))} size="small" sx={{ color: 'text.secondary' }}>
            <X size={18} />
          </IconButton>
        </DialogTitle>
        <DialogContent sx={{ pb: 3, pt: 1 }}>
          {/* Local Search input */}
          <Box sx={{ mb: 2.5 }}>
            <TextField
              fullWidth
              size="small"
              placeholder="Search table rows..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              slotProps={{
                input: {
                  startAdornment: (
                    <InputAdornment position="start">
                      <Search size={16} />
                    </InputAdornment>
                  ),
                  endAdornment: searchTerm && (
                    <InputAdornment position="end">
                      <IconButton size="small" onClick={() => setSearchTerm('')}>
                        <X size={14} />
                      </IconButton>
                    </InputAdornment>
                  )
                }
              }}
              sx={{
                '& .MuiOutlinedInput-root': {
                  background: 'rgba(255,255,255,0.02)',
                  borderColor: 'rgba(255,255,255,0.08)'
                }
              }}
            />
          </Box>

          {drillDown.loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', py: 8 }}>
              <CircularProgress color="secondary" />
            </Box>
          ) : filteredData.length === 0 ? (
            <Box sx={{ py: 6, textCenter: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
              <Typography variant="body1" color="text.secondary">No matching records found.</Typography>
            </Box>
          ) : (
            <TableContainer component={Paper} sx={{ maxHeight: 420, overflow: 'auto', background: 'rgba(17, 24, 39, 0.4)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <Table stickyHeader size="small">
                <TableHead>
                  <TableRow>
                    {drillDown.type === 'trainee' && (
                      <>
                        <TableCell sx={{ background: '#0b0f19', color: '#fff', fontWeight: 700 }}>Trainee ID</TableCell>
                        <TableCell sx={{ background: '#0b0f19', color: '#fff', fontWeight: 700 }}>Name</TableCell>
                        <TableCell sx={{ background: '#0b0f19', color: '#fff', fontWeight: 700 }}>DOJ</TableCell>
                        <TableCell sx={{ background: '#0b0f19', color: '#fff', fontWeight: 700 }}>DOL</TableCell>
                        <TableCell sx={{ background: '#0b0f19', color: '#fff', fontWeight: 700 }}>Scheme</TableCell>
                        <TableCell sx={{ background: '#0b0f19', color: '#fff', fontWeight: 700 }}>Status</TableCell>
                        <TableCell sx={{ background: '#0b0f19', color: '#fff', fontWeight: 700 }}>Current Eligibility</TableCell>
                      </>
                    )}
                    {drillDown.type === 'invoice' && (
                      <>
                        <TableCell sx={{ background: '#0b0f19', color: '#fff', fontWeight: 700 }}>Invoice Number</TableCell>
                        <TableCell sx={{ background: '#0b0f19', color: '#fff', fontWeight: 700 }}>Invoice Date</TableCell>
                        <TableCell sx={{ background: '#0b0f19', color: '#fff', fontWeight: 700 }}>Status</TableCell>
                        <TableCell sx={{ background: '#0b0f19', color: '#fff', fontWeight: 700 }} align="right">Billed Amount</TableCell>
                        <TableCell sx={{ background: '#0b0f19', color: '#fff', fontWeight: 700 }} align="right">Approved Amount</TableCell>
                        <TableCell sx={{ background: '#0b0f19', color: '#fff', fontWeight: 700 }} align="right">Rows Count</TableCell>
                      </>
                    )}
                    {drillDown.type === 'fraud' && (
                      <>
                        <TableCell sx={{ background: '#0b0f19', color: '#fff', fontWeight: 700 }}>Invoice No</TableCell>
                        <TableCell sx={{ background: '#0b0f19', color: '#fff', fontWeight: 700 }}>Trainee ID</TableCell>
                        <TableCell sx={{ background: '#0b0f19', color: '#fff', fontWeight: 700 }}>Rule Triggered</TableCell>
                        <TableCell sx={{ background: '#0b0f19', color: '#fff', fontWeight: 700 }}>Severity</TableCell>
                        <TableCell sx={{ background: '#0b0f19', color: '#fff', fontWeight: 700 }}>Details</TableCell>
                        <TableCell sx={{ background: '#0b0f19', color: '#fff', fontWeight: 700 }}>Recommended Action</TableCell>
                      </>
                    )}
                    {drillDown.type === 'ledger' && (
                      <>
                        <TableCell sx={{ background: '#0b0f19', color: '#fff', fontWeight: 700 }}>Trainee ID</TableCell>
                        <TableCell sx={{ background: '#0b0f19', color: '#fff', fontWeight: 700 }}>Trainee Name</TableCell>
                        <TableCell sx={{ background: '#0b0f19', color: '#fff', fontWeight: 700 }}>Invoice Number</TableCell>
                        <TableCell sx={{ background: '#0b0f19', color: '#fff', fontWeight: 700 }}>Payment Type</TableCell>
                        <TableCell sx={{ background: '#0b0f19', color: '#fff', fontWeight: 700 }} align="right">Amount Paid</TableCell>
                        <TableCell sx={{ background: '#0b0f19', color: '#fff', fontWeight: 700 }}>Payment Date</TableCell>
                      </>
                    )}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredData.map((row: any, idx: number) => (
                    <TableRow key={row.id || idx} hover sx={{ '&:last-child td, &:last-child th': { border: 0 } }}>
                      {drillDown.type === 'trainee' && (
                        <>
                          <TableCell sx={{ fontWeight: 600, color: '#6366f1' }}>{row.id}</TableCell>
                          <TableCell>{row.name}</TableCell>
                          <TableCell>{row.doj || 'N/A'}</TableCell>
                          <TableCell>{row.dol || 'Active'}</TableCell>
                          <TableCell>
                            <Chip label={row.scheme} size="small" variant="outlined" sx={{ fontSize: '0.68rem', fontWeight: 600 }} />
                          </TableCell>
                          <TableCell>
                            <Chip 
                              label={row.status} 
                              size="small" 
                              color={row.status === 'ACTIVE' ? 'success' : row.status === 'BLOCKED' ? 'error' : 'warning'}
                              sx={{ fontSize: '0.68rem', fontWeight: 700, height: 20 }}
                            />
                          </TableCell>
                          <TableCell>
                            {row.status === 'BLOCKED' ? (
                              <Tooltip title={row.blocked_reason || 'Blocked by rule engine'} placement="top">
                                <Typography variant="caption" sx={{ color: 'error.main', cursor: 'help', fontWeight: 600 }}>
                                  Blocked 🛈
                                </Typography>
                              </Tooltip>
                            ) : (
                              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                                {row.current_eligibility || 'Eligible'}
                              </Typography>
                            )}
                          </TableCell>
                        </>
                      )}
                      {drillDown.type === 'invoice' && (
                        <>
                          <TableCell sx={{ fontWeight: 600, color: '#06b6d4' }}>{row.invoice_number}</TableCell>
                          <TableCell>{row.invoice_date || 'N/A'}</TableCell>
                          <TableCell>
                            <Chip 
                              label={row.status} 
                              size="small" 
                              color={row.status === 'APPROVED' ? 'success' : row.status === 'EXCEPTION' ? 'error' : 'default'}
                              sx={{ fontSize: '0.68rem', fontWeight: 700, height: 20 }}
                            />
                          </TableCell>
                          <TableCell align="right" sx={{ fontWeight: 600 }}>{fmt(row.billed_amount)}</TableCell>
                          <TableCell align="right" sx={{ fontWeight: 600, color: '#10b981' }}>{fmt(row.approved_amount)}</TableCell>
                          <TableCell align="right">{row.record_count}</TableCell>
                        </>
                      )}
                      {drillDown.type === 'fraud' && (
                        <>
                          <TableCell sx={{ fontWeight: 600 }}>{row.invoice_number}</TableCell>
                          <TableCell sx={{ color: '#6366f1' }}>{row.trainee_id}</TableCell>
                          <TableCell sx={{ color: 'error.main', fontWeight: 600 }}>{row.rule_name}</TableCell>
                          <TableCell>
                            <Chip label={row.status} size="small" color="error" sx={{ fontSize: '0.65rem', fontWeight: 800, height: 18 }} />
                          </TableCell>
                          <TableCell sx={{ fontSize: '0.8rem', maxWidth: 260 }}>{row.message}</TableCell>
                          <TableCell sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>{row.recommended_action || 'N/A'}</TableCell>
                        </>
                      )}
                      {drillDown.type === 'ledger' && (
                        <>
                          <TableCell sx={{ color: '#6366f1', fontWeight: 600 }}>{row.trainee_id}</TableCell>
                          <TableCell>{row.trainee_name}</TableCell>
                          <TableCell>{row.invoice_number}</TableCell>
                          <TableCell>
                            <Chip label={row.payment_type} size="small" sx={{ fontSize: '0.65rem', fontWeight: 700 }} />
                          </TableCell>
                          <TableCell align="right" sx={{ fontWeight: 700, color: '#10b981' }}>{fmt(row.amount_paid)}</TableCell>
                          <TableCell>{row.payment_date}</TableCell>
                        </>
                      )}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2.5 }}>
          <Button onClick={() => setDrillDown(prev => ({ ...prev, open: false }))} variant="contained" color="secondary" size="small">
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
