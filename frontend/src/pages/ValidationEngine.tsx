import React, { useState, useEffect, useRef } from 'react';
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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemText,
  Alert,
  Divider
} from '@mui/material';
import { 
  Play, 
  CheckCircle, 
  XCircle, 
  Trash2, 
  AlertTriangle
} from 'lucide-react';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef } from 'ag-grid-community';
import api from '../api';

interface InvoiceSummary {
  invoice_number: string;
  invoice_date: string;
  record_count: number;
  billed_amount: number;
  approved_amount: number;
  status: string;
  exception_count: number;
  warning_count: number;
}

export const ValidationEngine: React.FC = () => {
  const [invoices, setInvoices] = useState<InvoiceSummary[]>([]);
  const [selectedInvoiceNumber, setSelectedInvoiceNumber] = useState<string>('');
  const [invoiceDetails, setInvoiceDetails] = useState<any[]>([]);
  const [loadingList, setLoadingList] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [gridLoading, setGridLoading] = useState(false);
  
  // Rule Violations Dialog
  const [violationsDialogOpen, setViolationsDialogOpen] = useState(false);
  const [selectedRecordName, setSelectedRecordName] = useState<string>('');
  const [violations, setViolations] = useState<any[]>([]);
  const [loadingViolations, setLoadingViolations] = useState(false);

  // Status message
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

  const gridRef = useRef<any>(null);

  const fetchInvoices = async () => {
    try {
      setLoadingList(true);
      const res = await api.get('/invoices');
      setInvoices(res.data);
      if (res.data.length > 0 && !selectedInvoiceNumber) {
        setSelectedInvoiceNumber(res.data[0].invoice_number);
      }
    } catch (err) {
      console.error("Failed to load invoices", err);
    } finally {
      setLoadingList(false);
    }
  };

  const fetchInvoiceRecords = async (invNo: string) => {
    if (!invNo) return;
    try {
      setGridLoading(true);
      const res = await api.get(`/invoices/${invNo}`);
      setInvoiceDetails(res.data);
    } catch (err) {
      console.error("Failed to load invoice records", err);
    } finally {
      setGridLoading(false);
    }
  };

  useEffect(() => {
    fetchInvoices();
  }, []);

  useEffect(() => {
    if (selectedInvoiceNumber) {
      fetchInvoiceRecords(selectedInvoiceNumber);
    } else {
      setInvoiceDetails([]);
    }
  }, [selectedInvoiceNumber]);

  const handleRunValidation = async () => {
    if (!selectedInvoiceNumber) return;
    try {
      setActionLoading(true);
      setStatusMessage(null);
      const res = await api.post(`/invoices/${selectedInvoiceNumber}/validate`);
      
      setStatusMessage({
        type: 'success',
        text: `Rules Validation Complete. Triggered ${res.data.error_count} errors, ${res.data.warning_count} warnings, and ${res.data.fraud_count} fraud incidents.`
      });

      // Reload
      await fetchInvoices();
      await fetchInvoiceRecords(selectedInvoiceNumber);
    } catch (err: any) {
      setStatusMessage({
        type: 'error',
        text: err.response?.data?.detail || 'Validation failed.'
      });
    } finally {
      setActionLoading(false);
    }
  };

  const handleApprove = async () => {
    if (!selectedInvoiceNumber) return;
    try {
      setActionLoading(true);
      setStatusMessage(null);
      await api.post(`/invoices/${selectedInvoiceNumber}/approve`);
      
      setStatusMessage({
        type: 'success',
        text: `Invoice ${selectedInvoiceNumber} has been approved. Payouts posted to ledger.`
      });

      await fetchInvoices();
      await fetchInvoiceRecords(selectedInvoiceNumber);
    } catch (err: any) {
      setStatusMessage({
        type: 'error',
        text: err.response?.data?.detail || 'Approval failed.'
      });
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!selectedInvoiceNumber) return;
    try {
      setActionLoading(true);
      setStatusMessage(null);
      await api.post(`/invoices/${selectedInvoiceNumber}/reject`);
      
      setStatusMessage({
        type: 'success',
        text: `Invoice ${selectedInvoiceNumber} has been rejected.`
      });

      await fetchInvoices();
      await fetchInvoiceRecords(selectedInvoiceNumber);
    } catch (err: any) {
      setStatusMessage({
        type: 'error',
        text: err.response?.data?.detail || 'Rejection failed.'
      });
    } finally {
      setActionLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedInvoiceNumber) return;
    if (!window.confirm("Are you sure you want to permanently delete this invoice and its records? This will also remove any posted payment ledger entries.")) return;
    try {
      setActionLoading(true);
      setStatusMessage(null);
      await api.delete(`/invoices/${selectedInvoiceNumber}`);
      
      setStatusMessage({
        type: 'success',
        text: `Invoice ${selectedInvoiceNumber} deleted successfully.`
      });

      setSelectedInvoiceNumber('');
      await fetchInvoices();
    } catch (err: any) {
      setStatusMessage({
        type: 'error',
        text: err.response?.data?.detail || 'Delete failed.'
      });
    } finally {
      setActionLoading(false);
    }
  };

  const handleShowViolations = async (recordId: number, name: string) => {
    setSelectedRecordName(name);
    try {
      setLoadingViolations(true);
      setViolationsDialogOpen(true);
      const res = await api.get(`/invoices/${selectedInvoiceNumber}/validation-details/${recordId}`);
      setViolations(res.data);
    } catch (err) {
      console.error("Failed to load violations details", err);
    } finally {
      setLoadingViolations(false);
    }
  };

  const currentInvoice = invoices.find(i => i.invoice_number === selectedInvoiceNumber);

  const AuditSeverityRenderer = (props: any) => {
    const severity = props.value;
    const recordId = props.data.id;
    const name = props.data.billed_name;

    if (severity === 'OK') {
      return <Chip label="PASSED" size="small" color="success" sx={{ fontWeight: 700, fontSize: '0.7rem', height: 20 }} />;
    }

    let color: 'error' | 'warning' | 'info' = 'info';
    if (severity === 'FRAUD') color = 'error';
    else if (severity === 'ERROR') color = 'warning';

    return (
      <Chip 
        label={`${severity} (${props.data.flags_count})`} 
        size="small" 
        color={color} 
        onClick={() => handleShowViolations(recordId, name)}
        sx={{ fontWeight: 800, fontSize: '0.7rem', height: 20, cursor: 'pointer' }}
      />
    );
  };

  const StatusChipRenderer = (props: any) => {
    const val = props.value;
    let color: 'success' | 'error' | 'warning' | 'info' | 'default' = 'default';
    if (val === 'APPROVED') color = 'success';
    else if (val === 'REJECTED') color = 'error';
    else if (val === 'EXCEPTION') color = 'warning';
    else if (val === 'VALIDATED') color = 'info';
    
    return <Chip label={val} size="small" color={color} sx={{ fontWeight: 700, fontSize: '0.75rem', height: 22 }} />;
  };

  const columnDefs: ColDef[] = [
    { field: 'trainee_id', headerName: 'Trainee ID', sortable: true, filter: true, width: 130 },
    { field: 'billed_name', headerName: 'Billed Name', sortable: true, filter: true, width: 200 },
    { field: 'billed_joining', headerName: 'Billed Join (₹)', width: 135, valueFormatter: params => params.value.toLocaleString() },
    { field: 'billed_180_days', headerName: 'Billed 180 (₹)', width: 135, valueFormatter: params => params.value.toLocaleString() },
    { field: 'billed_total', headerName: 'Billed Total (₹)', width: 145, valueFormatter: params => params.value.toLocaleString() },
    { field: 'approved_joining', headerName: 'Appr. Join (₹)', width: 135, valueFormatter: params => params.value.toLocaleString(), cellStyle: { color: '#34d399', fontWeight: 600 } },
    { field: 'approved_180_days', headerName: 'Appr. 180 (₹)', width: 135, valueFormatter: params => params.value.toLocaleString(), cellStyle: { color: '#34d399', fontWeight: 600 } },
    { field: 'approved_total', headerName: 'Appr. Total (₹)', width: 145, valueFormatter: params => params.value.toLocaleString(), cellStyle: { color: '#10b981', fontWeight: 700 } },
    { field: 'severity', headerName: 'Audit Result', cellRenderer: AuditSeverityRenderer, width: 135 },
    { field: 'status', headerName: 'Payout Status', cellRenderer: StatusChipRenderer, width: 125 }
  ];

  return (
    <Box className="fade-in-section">
      <Grid container spacing={3} sx={{ mb: 3 }}>
        {/* Selector Panel */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 2 }}>Audit Scope Selection</Typography>
              {loadingList ? (
                <CircularProgress size={24} />
              ) : invoices.length === 0 ? (
                <Typography variant="body2" sx={{ color: 'text.secondary' }}>No invoices uploaded. Go to Invoice Upload first.</Typography>
              ) : (
                <TextField
                  select
                  fullWidth
                  label="Select Invoice to Audit"
                  value={selectedInvoiceNumber}
                  onChange={(e) => setSelectedInvoiceNumber(e.target.value)}
                >
                  {invoices.map((inv) => (
                    <MenuItem key={inv.invoice_number} value={inv.invoice_number}>
                      {inv.invoice_number} ({inv.status})
                    </MenuItem>
                  ))}
                </TextField>
              )}

              {currentInvoice && (
                <Box sx={{ mt: 3, p: 2, borderRadius: 2, background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
                  <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1 }}>SELECTED FILE STATS</Typography>
                  <Grid container spacing={2}>
                    <Grid size={{ xs: 6 }}>
                      <Typography variant="caption" sx={{ color: 'text.secondary' }}>Date</Typography>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>{currentInvoice.invoice_date}</Typography>
                    </Grid>
                    <Grid size={{ xs: 6 }}>
                      <Typography variant="caption" sx={{ color: 'text.secondary' }}>Rows Count</Typography>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>{currentInvoice.record_count}</Typography>
                    </Grid>
                    <Grid size={{ xs: 6 }}>
                      <Typography variant="caption" sx={{ color: 'text.secondary' }}>Billed Sum</Typography>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>₹{currentInvoice.billed_amount.toLocaleString()}</Typography>
                    </Grid>
                    <Grid size={{ xs: 6 }}>
                      <Typography variant="caption" sx={{ color: 'text.secondary' }}>Approved Sum</Typography>
                      <Typography variant="body2" sx={{ fontWeight: 600, color: 'success.main' }}>₹{currentInvoice.approved_amount.toLocaleString()}</Typography>
                    </Grid>
                    <Grid size={{ xs: 12 }}>
                      <Typography variant="caption" sx={{ color: 'text.secondary' }}>Status</Typography>
                      <Box sx={{ mt: 0.5 }}>
                        <Chip label={currentInvoice.status} size="small" color={currentInvoice.status === 'APPROVED' ? 'success' : 'default'} sx={{ fontWeight: 700 }} />
                      </Box>
                    </Grid>
                  </Grid>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Audit Actions Panel */}
        <Grid size={{ xs: 12, md: 8 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 2 }}>Audit Execution Console</Typography>
              
              {statusMessage && (
                <Alert 
                  severity={statusMessage.type} 
                  sx={{ mb: 3, borderRadius: 2 }}
                  onClose={() => setStatusMessage(null)}
                >
                  {statusMessage.text}
                </Alert>
              )}

              {selectedInvoiceNumber ? (
                <Box>
                  <Typography variant="body2" sx={{ color: 'text.secondary', mb: 3 }}>
                    Execute automated checks on <b>{selectedInvoiceNumber}</b>. The system compares the data against the BDC registry, Separation records, and historical ledger payouts to calculate policy-compliant payouts.
                  </Typography>

                  <Grid container spacing={2}>
                    <Grid size={{ xs: 12, sm: 6 }}>
                      <Button
                        fullWidth
                        variant="contained"
                        color="secondary"
                        startIcon={<Play size={18} />}
                        disabled={actionLoading || currentInvoice?.status === 'APPROVED'}
                        onClick={handleRunValidation}
                        sx={{ py: 1.2 }}
                      >
                        {actionLoading ? <CircularProgress size={20} /> : 'Run Auditing & Rules Engine'}
                      </Button>
                    </Grid>

                    <Grid size={{ xs: 12, sm: 6 }}>
                      <Button
                        fullWidth
                        variant="contained"
                        color="success"
                        startIcon={<CheckCircle size={18} />}
                        disabled={actionLoading || currentInvoice?.status === 'APPROVED' || currentInvoice?.status === 'PENDING'}
                        onClick={handleApprove}
                        sx={{ py: 1.2 }}
                      >
                        Approve Invoice Payouts
                      </Button>
                    </Grid>

                    <Grid size={{ xs: 12, sm: 6 }}>
                      <Button
                        fullWidth
                        variant="outlined"
                        color="error"
                        startIcon={<XCircle size={18} />}
                        disabled={actionLoading || currentInvoice?.status === 'PENDING'}
                        onClick={handleReject}
                        sx={{ py: 1.2 }}
                      >
                        Reject Invoice
                      </Button>
                    </Grid>

                    <Grid size={{ xs: 12, sm: 6 }}>
                      <Button
                        fullWidth
                        variant="outlined"
                        color="error"
                        startIcon={<Trash2 size={18} />}
                        disabled={actionLoading}
                        onClick={handleDelete}
                        sx={{ py: 1.2 }}
                      >
                        Delete Ingested Sheet
                      </Button>
                    </Grid>
                  </Grid>
                </Box>
              ) : (
                <Typography variant="body2" sx={{ color: 'text.secondary', py: 2 }}>
                  Please select or upload an invoice workbook to view audit controls.
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* AG Grid Table displaying invoice lines */}
      {selectedInvoiceNumber && (
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
            <Typography variant="h6" sx={{ fontWeight: 700 }}>Invoice Line Items Registry</Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>*Click warning chips in 'Audit Result' to see rule violations.</Typography>
          </Box>
          <Box className="ag-theme-quartz ag-theme-quartz-dark" sx={{ height: 'calc(100vh - 380px)', width: '100%' }}>
            <AgGridReact
              ref={gridRef}
              rowData={invoiceDetails}
              columnDefs={columnDefs}
              pagination={true}
              paginationPageSize={20}
              animateRows={true}
              loading={gridLoading}
            />
          </Box>
        </Box>
      )}

      {/* Rule Violations Modal */}
      <Dialog 
        open={violationsDialogOpen} 
        onClose={() => setViolationsDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 800 }}>Audit Violations Details</DialogTitle>
        <DialogContent>
          <Typography variant="subtitle2" sx={{ mb: 2, color: 'primary.light' }}>
            Trainee Name: <b>{selectedRecordName}</b>
          </Typography>

          {loadingViolations ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}><CircularProgress size={24} /></Box>
          ) : violations.length === 0 ? (
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>No warnings found.</Typography>
          ) : (
            <List sx={{ p: 0 }}>
              {violations.map((v) => (
                <Box key={v.id} sx={{ mb: 2 }}>
                  <ListItem disablePadding sx={{ alignItems: 'flex-start', gap: 1 }}>
                    {v.status === 'FRAUD' ? (
                      <XCircle size={18} color="#ef4444" style={{ marginTop: 2 }} />
                    ) : (
                      <AlertTriangle size={18} color="#f59e0b" style={{ marginTop: 2 }} />
                    )}
                    <ListItemText
                      primary={
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                          <Typography variant="body2" sx={{ fontWeight: 700 }}>{v.rule_name}</Typography>
                          <Chip 
                            label={v.status} 
                            size="small" 
                            color={v.status === 'FRAUD' ? 'error' : v.status === 'ERROR' ? 'warning' : 'info'} 
                            sx={{ height: 16, fontSize: '0.55rem', fontWeight: 900 }}
                          />
                        </Box>
                      }
                      secondary={
                        <Box component="span" sx={{ display: 'block' }}>
                          {/* Reason Code Badge */}
                          {v.reason_code && (
                            <Box sx={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: 0.5,
                              mb: 0.75,
                              px: 1,
                              py: 0.25,
                              borderRadius: '4px',
                              background: 'rgba(20, 184, 166, 0.12)',
                              border: '1px solid rgba(20, 184, 166, 0.3)',
                            }}>
                              <Typography
                                component="span"
                                sx={{
                                  fontFamily: 'monospace',
                                  fontSize: '0.7rem',
                                  fontWeight: 700,
                                  color: 'hsl(174, 72%, 56%)',
                                  letterSpacing: '0.05em'
                                }}
                              >
                                {v.reason_code}
                              </Typography>
                            </Box>
                          )}
                          {/* Violation Message */}
                          <Typography component="span" variant="body2" sx={{ display: 'block', fontSize: '0.8rem', mt: 0.25, color: 'text.secondary' }}>
                            {v.message}
                          </Typography>
                          {/* Recommended Action */}
                          {v.recommended_action && (
                            <Box sx={{
                              display: 'flex',
                              alignItems: 'flex-start',
                              gap: 0.75,
                              mt: 0.75,
                              px: 1,
                              py: 0.5,
                              borderRadius: '4px',
                              background: 'rgba(16, 185, 129, 0.08)',
                              border: '1px solid rgba(16, 185, 129, 0.2)',
                            }}>
                              <Typography component="span" sx={{ fontSize: '0.65rem', fontWeight: 800, color: 'hsl(158, 64%, 52%)', mt: '1px', flexShrink: 0 }}>
                                ACTION:
                              </Typography>
                              <Typography component="span" sx={{ fontSize: '0.72rem', color: 'hsl(158, 40%, 70%)', lineHeight: 1.4 }}>
                                {v.recommended_action}
                              </Typography>
                            </Box>
                          )}
                        </Box>
                      }
                    />
                  </ListItem>
                  <Divider sx={{ mt: 1.5, borderColor: 'rgba(255,255,255,0.06)' }} />
                </Box>
              ))}
            </List>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setViolationsDialogOpen(false)} variant="contained" size="small">Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
