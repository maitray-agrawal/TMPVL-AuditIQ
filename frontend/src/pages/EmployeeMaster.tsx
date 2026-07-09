import React, { useState, useEffect, useRef } from 'react';
import { 
  Box, 
  Card, 
  CardContent, 
  Typography, 
  TextField, 
  MenuItem, 
  Drawer, 
  IconButton, 
  Grid, 
  Chip, 
  Button, 
  Dialog, 
  DialogTitle, 
  DialogContent, 
  DialogActions,
  Divider,
  List,
  ListItem,
  ListItemText
} from '@mui/material';
import { Search, X, Ban, ShieldAlert, CheckCircle, FileText, Coins, History } from 'lucide-react';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef } from 'ag-grid-community';
import api from '../api';

interface TraineeRow {
  id: string;
  name: string;
  doj: string;
  dol: string | null;
  scheme: string;
  status: string;
  blocked_reason: string | null;
  aadhaar?: string | null;
  ticket_number?: string | null;
  category?: string | null;
  batch?: string | null;
  shop?: string | null;
  lifecycle_number?: number;
  current_eligibility?: string;
}

export const EmployeeMaster: React.FC = () => {
  const [rowData, setRowData] = useState<TraineeRow[]>([]);
  const [searchText, setSearchText] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [schemeFilter, setSchemeFilter] = useState('');
  
  // Drawer states
  const [selectedTraineeId, setSelectedTraineeId] = useState<string | null>(null);
  const [details, setDetails] = useState<any | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  
  // Block Dialog states
  const [blockDialogOpen, setBlockDialogOpen] = useState(false);
  const [blockReason, setBlockReason] = useState('');

  const [loading, setLoading] = useState(false);

  const gridRef = useRef<any>(null);

  const fetchTrainees = async () => {
    try {
      setLoading(true);
      const res = await api.get('/trainees', {
        params: {
          search: searchText || undefined,
          status: statusFilter || undefined,
          scheme: schemeFilter || undefined
        }
      });
      setRowData(res.data);
    } catch (err) {
      console.error("Failed to load trainees", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTrainees();
  }, [searchText, statusFilter, schemeFilter]);

  const fetchTraineeDetails = async (id: string) => {
    try {
      const res = await api.get(`/trainees/${id}`);
      setDetails(res.data);
      setDrawerOpen(true);
    } catch (err) {
      console.error("Failed to fetch trainee details", err);
    }
  };

  const handleRowClicked = (event: any) => {
    const traineeId = event.data.id;
    setSelectedTraineeId(traineeId);
    fetchTraineeDetails(traineeId);
  };

  const handleBlockTrainee = async () => {
    if (!selectedTraineeId) return;
    try {
      await api.post(`/trainees/${selectedTraineeId}/block`, { reason: blockReason });
      setBlockDialogOpen(false);
      setBlockReason('');
      // Reload details and grid
      fetchTraineeDetails(selectedTraineeId);
      fetchTrainees();
    } catch (err) {
      console.error("Error blocking trainee", err);
    }
  };

  const handleUnblockTrainee = async () => {
    if (!selectedTraineeId) return;
    try {
      await api.post(`/trainees/${selectedTraineeId}/unblock`);
      // Reload details and grid
      fetchTraineeDetails(selectedTraineeId);
      fetchTrainees();
    } catch (err) {
      console.error("Error unblocking trainee", err);
    }
  };


  const LifecycleStatusRenderer = (props: any) => {
    const val = props.data.status;
    const lNum = props.data.lifecycle_number || 1;
    let color: "success" | "error" | "default" = "default";
    if (val === 'ACTIVE') color = 'success';
    else if (val === 'BLOCKED') color = 'error';
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, height: '100%' }}>
        <Chip 
          label={val} 
          size="small" 
          color={color} 
          sx={{ fontWeight: 700, fontSize: '0.75rem', height: 22 }} 
        />
        <Typography variant="body2" sx={{ fontSize: '0.75rem', fontWeight: 600, color: 'text.secondary' }}>
          (L{lNum})
        </Typography>
      </Box>
    );
  };

  const columnDefs: ColDef[] = [
    { field: 'id', headerName: 'Trainee ID', sortable: true, filter: true, width: 140 },
    { field: 'name', headerName: 'Full Name', sortable: true, filter: true, width: 220, flex: 1 },
    { field: 'doj', headerName: 'Date of Joining', sortable: true, width: 140 },
    { field: 'dol', headerName: 'Date of Leaving', sortable: true, width: 140, valueFormatter: params => params.value || 'N/A' },
    { field: 'scheme', headerName: 'Scheme', sortable: true, filter: true, width: 120 },
    { field: 'category', headerName: 'Category', sortable: true, filter: true, width: 120, valueFormatter: params => params.value || 'N/A' },
    { field: 'batch', headerName: 'Batch', sortable: true, filter: true, width: 120, valueFormatter: params => params.value || 'N/A' },
    { field: 'shop', headerName: 'Shop', sortable: true, filter: true, width: 120, valueFormatter: params => params.value || 'N/A' },
    { field: 'aadhaar', headerName: 'Aadhaar', sortable: true, filter: true, width: 150, valueFormatter: params => params.value || 'N/A' },
    { field: 'ticket_number', headerName: 'Ticket Number', sortable: true, filter: true, width: 150, valueFormatter: params => params.value || 'N/A' },
    { field: 'status', headerName: 'Lifecycle Status', sortable: true, cellRenderer: LifecycleStatusRenderer, width: 160 },
  ];

  return (
    <Box className="fade-in-section">
      <Card sx={{ mb: 3 }}>
        <CardContent sx={{ p: '24px !important' }}>
          <Grid container spacing={2} sx={{ alignItems: 'center' }}>
            {/* Search Input */}
            <Grid size={{ xs: 12, md: 5 }}>
              <TextField
                fullWidth
                size="small"
                placeholder="Search by ID or Name..."
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                slotProps={{
                  input: {
                    startAdornment: <Search size={18} style={{ marginRight: 8, color: '#9ca3af' }} />
                  }
                }}
              />
            </Grid>

            {/* Scheme Filter */}
            <Grid size={{ xs: 12, sm: 6, md: 3.5 }}>
              <TextField
                select
                fullWidth
                size="small"
                label="Scheme Filter"
                value={schemeFilter}
                onChange={(e) => setSchemeFilter(e.target.value)}
              >
                <MenuItem value="">All Schemes</MenuItem>
                <MenuItem value="NAPS">NAPS</MenuItem>
                <MenuItem value="B.Tech">B.Tech</MenuItem>
                <MenuItem value="M.Tech">M.Tech</MenuItem>
              </TextField>
            </Grid>

            {/* Status Filter */}
            <Grid size={{ xs: 12, sm: 6, md: 3.5 }}>
              <TextField
                select
                fullWidth
                size="small"
                label="Status Filter"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <MenuItem value="">All Statuses</MenuItem>
                <MenuItem value="ACTIVE">ACTIVE</MenuItem>
                <MenuItem value="SEPARATED">SEPARATED</MenuItem>
                <MenuItem value="BLOCKED">BLOCKED</MenuItem>
              </TextField>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* AG Grid Container */}
      <Box className="ag-theme-quartz ag-theme-quartz-dark" sx={{ height: 'calc(100vh - 280px)', width: '100%' }}>
        <AgGridReact
          ref={gridRef}
          rowData={rowData}
          columnDefs={columnDefs}
          pagination={true}
          paginationPageSize={20}
          onRowClicked={handleRowClicked}
          rowSelection="single"
          animateRows={true}
          loading={loading}
        />
      </Box>

      {/* Trainee Details Drawer */}
      <Drawer
        anchor="right"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        slotProps={{
          paper: {
            sx: {
              width: 500,
              background: '#0f172a',
              borderLeft: '1px solid rgba(255,255,255,0.08)',
              p: 3,
            }
          }
        }}
      >
        {details && (
          <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            {/* Header */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
              <Typography variant="h5" sx={{ fontWeight: 800 }}>Trainee File</Typography>
              <IconButton onClick={() => setDrawerOpen(false)} sx={{ color: 'text.secondary' }}>
                <X size={20} />
              </IconButton>
            </Box>

            {/* Profile Info */}
            <Box sx={{ p: 2.5, borderRadius: 3, background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', mb: 3 }}>
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 1.5, color: '#fff' }}>{details.profile.name}</Typography>
              
              <Grid container spacing={1.5}>
                <Grid size={{ xs: 6 }}>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>TRAINEE ID</Typography>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>{details.profile.id}</Typography>
                </Grid>
                <Grid size={{ xs: 6 }}>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>SCHEME</Typography>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>{details.profile.scheme}</Typography>
                </Grid>
                <Grid size={{ xs: 6 }}>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>CATEGORY</Typography>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>{details.profile.category || 'N/A'}</Typography>
                </Grid>
                <Grid size={{ xs: 6 }}>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>BATCH</Typography>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>{details.profile.batch || 'N/A'}</Typography>
                </Grid>
                <Grid size={{ xs: 6 }}>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>SHOP</Typography>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>{details.profile.shop || 'N/A'}</Typography>
                </Grid>
                <Grid size={{ xs: 6 }}>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>LIFECYCLE NO.</Typography>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>{details.profile.lifecycle_number || 1}</Typography>
                </Grid>
                <Grid size={{ xs: 6 }}>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>DATE OF JOINING</Typography>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>{details.profile.doj}</Typography>
                </Grid>
                <Grid size={{ xs: 6 }}>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>DATE OF LEAVING</Typography>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>{details.profile.dol || 'N/A'}</Typography>
                </Grid>
                <Grid size={{ xs: 6 }}>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>AADHAAR</Typography>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>{details.profile.aadhaar || 'N/A'}</Typography>
                </Grid>
                <Grid size={{ xs: 6 }}>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>TICKET NUMBER</Typography>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>{details.profile.ticket_number || 'N/A'}</Typography>
                </Grid>
                <Grid size={{ xs: 6 }}>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>COMPLIANCE STATUS</Typography>
                  <Box sx={{ mt: 0.5 }}>
                    <Chip 
                      label={details.profile.status} 
                      size="small" 
                      color={details.profile.status === 'ACTIVE' ? 'success' : details.profile.status === 'BLOCKED' ? 'error' : 'default'}
                      sx={{ fontWeight: 700 }}
                    />
                  </Box>
                </Grid>
              </Grid>

              {details.profile.status === 'BLOCKED' && (
                <Box sx={{ mt: 2, p: 1.5, borderRadius: 2, background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
                  <Typography variant="caption" sx={{ color: 'error.main', fontWeight: 700, display: 'block', mb: 0.5 }}>BLOCK REASON</Typography>
                  <Typography variant="body2" sx={{ fontSize: '0.85rem' }}>{details.profile.blocked_reason}</Typography>
                </Box>
              )}
            </Box>

            {/* Block / Unblock Action Button */}
            <Box sx={{ mb: 3 }}>
              {details.profile.status === 'BLOCKED' ? (
                <Button 
                  fullWidth 
                  variant="outlined" 
                  color="success" 
                  startIcon={<CheckCircle size={16} />}
                  onClick={handleUnblockTrainee}
                >
                  Unblock Trainee (Allow Payments)
                </Button>
              ) : (
                <Button 
                  fullWidth 
                  variant="outlined" 
                  color="error" 
                  startIcon={<Ban size={16} />}
                  onClick={() => setBlockDialogOpen(true)}
                >
                  Block Trainee (Flag Fraud & Halt)
                </Button>
              )}
            </Box>

            <Divider sx={{ borderColor: 'rgba(255,255,255,0.08)', mb: 3 }} />

            {/* Payment Summary */}
            {details.payment_summary && (
              <Box sx={{ mb: 3, p: 2.5, borderRadius: 3, background: 'rgba(99, 102, 241, 0.03)', border: '1px solid rgba(99, 102, 241, 0.15)' }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 2, color: '#818cf8', display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Coins size={18} /> Payment Summary
                </Typography>
                <Grid container spacing={2}>
                  <Grid size={{ xs: 4 }}>
                    <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>JOINING PAID</Typography>
                    <Typography variant="body2" sx={{ fontWeight: 700, color: 'success.main' }}>₹{details.payment_summary.joining_paid}</Typography>
                    <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.7rem' }}>Bal: ₹{details.payment_summary.joining_remaining}</Typography>
                  </Grid>
                  <Grid size={{ xs: 4 }}>
                    <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>180-DAYS PAID</Typography>
                    <Typography variant="body2" sx={{ fontWeight: 700, color: 'success.main' }}>₹{details.payment_summary.days180_paid}</Typography>
                    <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.7rem' }}>Bal: ₹{details.payment_summary.days180_remaining}</Typography>
                  </Grid>
                  <Grid size={{ xs: 4 }}>
                    <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>TOTAL PAID</Typography>
                    <Typography variant="body2" sx={{ fontWeight: 800, color: '#818cf8' }}>₹{details.payment_summary.total_paid}</Typography>
                    <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.7rem' }}>Bal: ₹{details.payment_summary.total_remaining}</Typography>
                  </Grid>
                </Grid>
              </Box>
            )}

            <Divider sx={{ borderColor: 'rgba(255,255,255,0.08)', mb: 3 }} />

            <Box sx={{ flexGrow: 1, overflowY: 'auto' }}>
              {/* Separation History Timeline */}
              <Box sx={{ mb: 3 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <History size={18} color="#f59e0b" /> Separation History
                </Typography>
                {(!details.separation_history || details.separation_history.length === 0) ? (
                  <Typography variant="body2" sx={{ color: 'text.secondary', py: 1 }}>
                    No separation records logged.
                  </Typography>
                ) : (
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                    {details.separation_history.map((s: any) => (
                      <Box 
                        key={s.id}
                        sx={{ 
                          p: 1.5,
                          borderRadius: 2,
                          background: 'rgba(255, 255, 255, 0.01)',
                          border: '1px solid rgba(255, 255, 255, 0.05)',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 0.5
                        }}
                      >
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="body2" sx={{ fontWeight: 700, color: '#f59e0b' }}>
                            {s.month}
                          </Typography>
                          <Chip 
                            label={s.status_after} 
                            size="small" 
                            color={s.status_after === 'BLOCKED' ? 'error' : 'default'}
                            sx={{ height: 18, fontSize: '0.65rem', fontWeight: 700 }}
                          />
                        </Box>
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                          Workbook: {s.workbook} (Sheet: {s.sheet})
                        </Typography>
                        <Typography variant="body2" sx={{ fontSize: '0.8rem' }}>
                          Leaving Date: {s.dol} | Tenure: {s.tenure} days
                        </Typography>
                        <Typography variant="body2" sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>
                          Reason: {s.reason} | Transition: {s.status_before} → {s.status_after}
                        </Typography>
                      </Box>
                    ))}
                  </Box>
                )}
              </Box>

              <Divider sx={{ borderColor: 'rgba(255,255,255,0.08)', mb: 3 }} />

              {/* Historical Payments Ledger */}
              <Box sx={{ mb: 3 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <FileText size={18} color="#6366f1" /> Payout Ledger History
                </Typography>

                {details.payment_history.length === 0 ? (
                  <Typography variant="body2" sx={{ color: 'text.secondary', py: 1 }}>
                    No approved ledger payments logged.
                  </Typography>
                ) : (
                  <List sx={{ p: 0 }}>
                    {details.payment_history.map((h: any) => (
                      <ListItem 
                        key={h.id}
                        sx={{ 
                          border: '1px solid rgba(255,255,255,0.06)',
                          borderRadius: 2,
                          mb: 1,
                          background: 'rgba(255,255,255,0.01)',
                          display: 'flex',
                          justifyContent: 'space-between',
                        }}
                      >
                        <ListItemText
                          primary={
                            <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.9rem', color: 'text.primary' }}>
                              {h.payment_type} Payment
                            </Typography>
                          }
                          secondary={
                            <Typography component="span" variant="caption" sx={{ display: 'block', fontSize: '0.75rem', color: 'text.secondary' }}>
                              Invoice: {h.invoice_number} • Date: {h.payment_date}
                            </Typography>
                          }
                        />
                        <Typography variant="body1" sx={{ fontWeight: 700, color: 'success.main' }}>
                          +₹{h.amount_paid}
                        </Typography>
                      </ListItem>
                    ))}
                  </List>
                )}
              </Box>

              <Divider sx={{ borderColor: 'rgba(255,255,255,0.08)', mb: 3 }} />

              {/* Invoice Claims History */}
              <Box sx={{ mb: 3 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <History size={18} color="#f43f5e" /> Invoice Claims History
                </Typography>
                {(!details.invoice_timeline || details.invoice_timeline.length === 0) ? (
                  <Typography variant="body2" sx={{ color: 'text.secondary', py: 1 }}>
                    No invoice claims logged.
                  </Typography>
                ) : (
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                    {details.invoice_timeline.map((item: any) => (
                      <Box 
                        key={item.id}
                        sx={{ 
                          p: 1.5,
                          borderRadius: 2,
                          background: 'rgba(255, 255, 255, 0.01)',
                          border: '1px solid rgba(255, 255, 255, 0.05)',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 0.5
                        }}
                      >
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="body2" sx={{ fontWeight: 700, color: '#f43f5e' }}>
                            Invoice: {item.invoice_number}
                          </Typography>
                          <Chip 
                            label={item.status} 
                            size="small" 
                            color={item.status === 'APPROVED' ? 'success' : item.status === 'FRAUD' ? 'error' : item.status === 'PARTIALLY_APPROVED' ? 'warning' : 'default'}
                            sx={{ height: 18, fontSize: '0.65rem', fontWeight: 700 }}
                          />
                        </Box>
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                          Date: {item.invoice_date}
                        </Typography>
                        <Typography variant="body2" sx={{ fontSize: '0.8rem' }}>
                          Claimed: ₹{item.claimed_amount} | Approved: ₹{item.approved_amount} | Rejected: ₹{item.rejected_amount}
                        </Typography>
                        <Typography variant="body2" sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>
                          Risk Score: <span style={{ fontWeight: 700, color: item.fraud_score > 50 ? '#ef4444' : item.fraud_score > 20 ? '#f59e0b' : '#10b981' }}>{item.fraud_score} ({item.fraud_category})</span>
                        </Typography>
                        {item.reason && (
                          <Typography variant="body2" sx={{ fontSize: '0.8rem', color: 'error.main', mt: 0.5 }}>
                            Reason: {item.reason}
                          </Typography>
                        )}
                      </Box>
                    ))}
                  </Box>
                )}
              </Box>

              <Divider sx={{ borderColor: 'rgba(255,255,255,0.08)', mb: 3 }} />

              {/* Audit Warnings */}
              <Box>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <ShieldAlert size={18} color="#f59e0b" /> Audit Warnings
                </Typography>

                {details.violations.length === 0 ? (
                  <Typography variant="body2" sx={{ color: 'text.secondary', py: 1 }}>
                    No warnings or exception logs triggered.
                  </Typography>
                ) : (
                  <List sx={{ p: 0 }}>
                    {details.violations.map((v: any) => (
                      <ListItem 
                        key={v.id}
                        sx={{ 
                          border: '1px solid rgba(255,255,255,0.06)',
                          borderRadius: 2,
                          mb: 1,
                          background: 'rgba(255,255,255,0.01)',
                        }}
                      >
                        <ListItemText
                          primary={
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <Typography variant="body2" sx={{ fontWeight: 700 }}>{v.rule_name}</Typography>
                              <Chip 
                                label={v.status} 
                                size="small" 
                                color={v.status === 'FRAUD' ? 'error' : v.status === 'ERROR' ? 'warning' : 'info'}
                                sx={{ height: 16, fontSize: '0.6rem', fontWeight: 800 }}
                              />
                            </Box>
                          }
                          secondary={
                            <Typography component="span" variant="body2" sx={{ display: 'block', fontSize: '0.75rem', mt: 0.5, color: 'text.secondary' }}>
                              {v.message}
                            </Typography>
                          }
                        />
                      </ListItem>
                    ))}
                  </List>
                )}
              </Box>
            </Box>
          </Box>
        )}
      </Drawer>

      {/* Block Confirmation Dialog */}
      <Dialog open={blockDialogOpen} onClose={() => setBlockDialogOpen(false)}>
        <DialogTitle sx={{ fontWeight: 700 }}>Block Trainee Payouts</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ mb: 2, color: 'text.secondary' }}>
            Blocking this trainee will permanently flag their records, set status to BLOCKED, and reject all pending/future invoice payouts unless manually unblocked.
          </Typography>
          <TextField
            autoFocus
            margin="dense"
            label="Reason for blocking"
            fullWidth
            variant="outlined"
            multiline
            rows={3}
            value={blockReason}
            onChange={(e) => setBlockReason(e.target.value)}
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2.5 }}>
          <Button onClick={() => setBlockDialogOpen(false)} variant="outlined">Cancel</Button>
          <Button onClick={handleBlockTrainee} variant="contained" color="error">Block Trainee</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
