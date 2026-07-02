import React, { useEffect, useState, useRef } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  TextField,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Stack,
} from '@mui/material';
import {
  Visibility as VisibilityIcon,
  Close as CloseIcon,
  Search as SearchIcon,
  RotateLeft as ResetIcon,
} from '@mui/icons-material';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef } from 'ag-grid-community';
import api from '../api';

interface LogRow {
  id: number;
  timestamp: string;
  action: string;
  module: string;
  details: string;
  operator: string | null;
  workbook: string | null;
  sheet: string | null;
  rows_count: number | null;
  duration: number | null;
  inserted: number | null;
  updated: number | null;
  failed: number | null;
  warnings: number | null;
  errors: number | null;
  before_state: any;
  after_state: any;
  employee_id: string | null;
  invoice_number: string | null;
}

export const AuditLogs: React.FC = () => {
  const [rowData, setRowData] = useState<LogRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedLog, setSelectedLog] = useState<LogRow | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Filters state
  const [employeeId, setEmployeeId] = useState('');
  const [invoiceNumber, setInvoiceNumber] = useState('');
  const [workbook, setWorkbook] = useState('');
  const [action, setAction] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const gridRef = useRef<any>(null);

  const fetchLogs = async () => {
    try {
      setLoading(true);
      const params: any = { limit: 1000 };
      if (employeeId.trim()) params.employee_id = employeeId.trim();
      if (invoiceNumber.trim()) params.invoice_number = invoiceNumber.trim();
      if (workbook.trim()) params.workbook = workbook.trim();
      if (action) params.action = action;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;

      const res = await api.get('/logs', { params });
      setRowData(res.data);
    } catch (err) {
      console.error("Failed to load audit logs", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchLogs();
  };

  const handleReset = () => {
    setEmployeeId('');
    setInvoiceNumber('');
    setWorkbook('');
    setAction('');
    setDateFrom('');
    setDateTo('');
    // Direct trigger with empty parameters
    setTimeout(() => {
      api.get('/logs', { params: { limit: 1000 } }).then(res => {
        setRowData(res.data);
      }).catch(err => console.error(err));
    }, 50);
  };

  const handleOpenDetails = (log: LogRow) => {
    setSelectedLog(log);
    setIsModalOpen(true);
  };

  const handleCloseDetails = () => {
    setSelectedLog(null);
    setIsModalOpen(false);
  };

  const ActionCellRenderer = (params: any) => {
    const act = params.value || '';
    let color = 'info';
    if (act.includes('IMPORT_BDC')) color = 'success';
    else if (act.includes('IMPORT_SEPARATION')) color = 'warning';
    else if (act.includes('IMPORT_INVOICE')) color = 'secondary';
    else if (act.includes('RUN_VALIDATION')) color = 'primary';
    else if (act.includes('APPROVE')) color = 'success';
    else if (act.includes('REJECT') || act.includes('DELETE')) color = 'error';

    return (
      <Chip
        label={act}
        color={color as any}
        size="small"
        sx={{ fontWeight: 600, fontSize: '0.7rem', borderRadius: '6px' }}
      />
    );
  };

  const columnDefs: ColDef[] = [
    { field: 'timestamp', headerName: 'Timestamp (UTC)', sortable: true, width: 170, cellClass: 'monospace-cell' },
    { field: 'action', headerName: 'Action Type', sortable: true, filter: true, width: 220, cellRenderer: ActionCellRenderer },
    { field: 'operator', headerName: 'Operator', sortable: true, filter: true, width: 110 },
    { field: 'workbook', headerName: 'Workbook / File', sortable: true, filter: true, width: 180 },
    { field: 'sheet', headerName: 'Sheet', sortable: true, filter: true, width: 110 },
    { field: 'rows_count', headerName: 'Rows', sortable: true, width: 85, type: 'numericColumn' },
    { 
      field: 'duration', 
      headerName: 'Duration', 
      sortable: true, 
      width: 95, 
      type: 'numericColumn',
      valueFormatter: (params) => params.value != null ? `${Number(params.value).toFixed(2)}s` : '-'
    },
    { field: 'details', headerName: 'Details', sortable: true, filter: true, width: 280, flex: 1 },
    {
      headerName: 'View',
      width: 80,
      pinned: 'right',
      sortable: false,
      filter: false,
      cellRenderer: (params: any) => (
        <IconButton
          color="secondary"
          size="small"
          onClick={() => handleOpenDetails(params.data)}
          sx={{
            '&:hover': {
              backgroundColor: 'rgba(6, 182, 212, 0.1)',
            }
          }}
        >
          <VisibilityIcon fontSize="small" />
        </IconButton>
      )
    }
  ];

  const actionTypes = [
    'IMPORT_BDC_SHEET',
    'IMPORT_BDC_WORKBOOK',
    'IMPORT_SEPARATION_SHEET',
    'IMPORT_SEPARATION_WORKBOOK',
    'IMPORT_INVOICE',
    'RUN_VALIDATION',
    'APPROVE_INVOICE',
    'REJECT_INVOICE',
    'DELETE_INVOICE',
    'BLOCK_TRAINEE',
    'UNBLOCK_TRAINEE',
    'GENERATE_APPROVED_INVOICE_REPORT',
    'GENERATE_EXCEPTION_REPORT',
    'GENERATE_FRAUD_REPORT',
    'GENERATE_PAYMENT_SUMMARY_REPORT',
    'GENERATE_AUDIT_REPORT',
    'GENERATE_REJECTED_INVOICE_REPORT',
    'GENERATE_CORRECTED_INVOICE_REPORT',
    'GENERATE_VENDOR_PAYMENT_SUMMARY',
    'GENERATE_FINANCE_SUMMARY_REPORT',
    'GENERATE_FINANCE_ANALYTICS_REPORT',
  ];

  return (
    <Box className="fade-in-section" sx={{ display: 'flex', flexDirection: 'column', gap: 3, height: '100%' }}>
      {/* Title block */}
      <Card>
        <CardContent sx={{ p: 3 }}>
          <Typography variant="h5" sx={{ fontWeight: 700, mb: 1, background: 'linear-gradient(90deg, #6366f1, #06b6d4)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            System Operations Audit Log
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', maxHeight: '40px' }}>
            This immutable ledger contains system-wide operations, file uploads, reconciliations, approvals, and report generation events for enterprise IT audit compliance.
          </Typography>
        </CardContent>
      </Card>

      {/* Filter panel */}
      <Card sx={{ p: 2 }}>
        <form onSubmit={handleSearch}>
          <Grid container spacing={2} sx={{ alignItems: 'center' }}>
            <Grid size={{ xs: 12, sm: 6, md: 2 }}>
              <TextField
                fullWidth
                size="small"
                label="Employee ID"
                value={employeeId}
                onChange={(e) => setEmployeeId(e.target.value)}
                placeholder="e.g. T001"
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 2 }}>
              <TextField
                fullWidth
                size="small"
                label="Invoice Number"
                value={invoiceNumber}
                onChange={(e) => setInvoiceNumber(e.target.value)}
                placeholder="e.g. INV-01"
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 2 }}>
              <TextField
                fullWidth
                size="small"
                label="Workbook Name"
                value={workbook}
                onChange={(e) => setWorkbook(e.target.value)}
                placeholder="e.g. BDC_Master"
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 2 }}>
              <FormControl fullWidth size="small">
                <InputLabel>Action/Operation</InputLabel>
                <Select
                  value={action}
                  label="Action/Operation"
                  onChange={(e) => setAction(e.target.value)}
                >
                  <MenuItem value=""><em>All Operations</em></MenuItem>
                  {actionTypes.map(act => (
                    <MenuItem key={act} value={act}>{act}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 1.5 }}>
              <TextField
                fullWidth
                size="small"
                label="Date From"
                type="date"
                slotProps={{ inputLabel: { shrink: true } }}
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 1.5 }}>
              <TextField
                fullWidth
                size="small"
                label="Date To"
                type="date"
                slotProps={{ inputLabel: { shrink: true } }}
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 1 }} sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end', ml: 'auto' }}>
              <Button
                variant="contained"
                color="primary"
                type="submit"
                size="medium"
                startIcon={<SearchIcon />}
                disabled={loading}
              >
                Find
              </Button>
              <Button
                variant="outlined"
                color="secondary"
                onClick={handleReset}
                size="medium"
                startIcon={<ResetIcon />}
                disabled={loading}
              >
                Clear
              </Button>
            </Grid>
          </Grid>
        </form>
      </Card>

      {/* Grid container */}
      <Box className="ag-theme-quartz ag-theme-quartz-dark" sx={{ flexGrow: 1, height: 'calc(100vh - 350px)', width: '100%' }}>
        <AgGridReact
          ref={gridRef}
          rowData={rowData}
          columnDefs={columnDefs}
          pagination={true}
          paginationPageSize={25}
          animateRows={true}
          loading={loading}
          overlayNoRowsTemplate="<span>No system logs found matching the filter criteria.</span>"
        />
      </Box>

      {/* Details modal */}
      {selectedLog && (
        <Dialog
          open={isModalOpen}
          onClose={handleCloseDetails}
          maxWidth="lg"
          fullWidth
          slotProps={{
            paper: {
              sx: {
                background: 'rgba(17, 24, 39, 0.95)',
                backdropFilter: 'blur(20px)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                boxShadow: '0 20px 50px rgba(0, 0, 0, 0.5)',
                borderRadius: 4
              }
            }
          }}
        >
          <DialogTitle sx={{ m: 0, p: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 700, color: 'text.primary' }}>
                Audit Log Details
              </Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                Log ID: {selectedLog.id} &bull; Timestamp: {selectedLog.timestamp} UTC
              </Typography>
            </Box>
            <IconButton onClick={handleCloseDetails} color="secondary">
              <CloseIcon />
            </IconButton>
          </DialogTitle>

          <DialogContent sx={{ p: 3 }}>
            <Grid container spacing={3} sx={{ mb: 4 }}>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Typography variant="caption" color="text.secondary">Action Type</Typography>
                <Box sx={{ mt: 0.5 }}>
                  <Chip
                    label={selectedLog.action}
                    color={
                      selectedLog.action.includes('IMPORT_BDC') ? 'success' :
                      selectedLog.action.includes('IMPORT_SEPARATION') ? 'warning' :
                      selectedLog.action.includes('IMPORT_INVOICE') ? 'secondary' :
                      selectedLog.action.includes('RUN_VALIDATION') ? 'primary' :
                      selectedLog.action.includes('APPROVE') ? 'success' :
                      selectedLog.action.includes('REJECT') || selectedLog.action.includes('DELETE') ? 'error' : 'info'
                    }
                    size="small"
                    sx={{ fontWeight: 600 }}
                  />
                </Box>
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Typography variant="caption" color="text.secondary">Operator</Typography>
                <Typography variant="body1" sx={{ fontWeight: 500 }}>{selectedLog.operator || 'System'}</Typography>
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Typography variant="caption" color="text.secondary">Workbook / File</Typography>
                <Typography variant="body1" sx={{ fontWeight: 500 }}>{selectedLog.workbook || 'N/A'}</Typography>
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Typography variant="caption" color="text.secondary">Sheet Name</Typography>
                <Typography variant="body1" sx={{ fontWeight: 500 }}>{selectedLog.sheet || 'N/A'}</Typography>
              </Grid>

              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Typography variant="caption" color="text.secondary">Rows Processed</Typography>
                <Typography variant="body1" sx={{ fontWeight: 500 }}>{selectedLog.rows_count != null ? selectedLog.rows_count : 'N/A'}</Typography>
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Typography variant="caption" color="text.secondary">Operation Duration</Typography>
                <Typography variant="body1" sx={{ fontWeight: 500 }}>{selectedLog.duration != null ? `${Number(selectedLog.duration).toFixed(2)}s` : 'N/A'}</Typography>
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Typography variant="caption" color="text.secondary">Invoice Number</Typography>
                <Typography variant="body1" sx={{ fontWeight: 500, color: selectedLog.invoice_number ? 'secondary.light' : 'text.primary' }}>
                  {selectedLog.invoice_number || 'N/A'}
                </Typography>
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Typography variant="caption" color="text.secondary">Trainee / Employee ID</Typography>
                <Typography variant="body1" sx={{ fontWeight: 500, color: selectedLog.employee_id ? 'primary.light' : 'text.primary' }}>
                  {selectedLog.employee_id || 'N/A'}
                </Typography>
              </Grid>
            </Grid>

            {/* Counts dashboard */}
            {(selectedLog.inserted != null || selectedLog.updated != null || selectedLog.failed != null || selectedLog.warnings != null || selectedLog.errors != null) && (
              <Box sx={{ mb: 4, p: 2, bgcolor: 'rgba(255,255,255,0.02)', borderRadius: 3, border: '1px solid rgba(255,255,255,0.05)' }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 2, color: 'text.primary' }}>Operation Counts</Typography>
                <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: 'wrap' }}>
                  {selectedLog.inserted != null && (
                    <Box sx={{ flex: '1 1 18%', p: 1.5, textAlign: 'center', bgcolor: 'rgba(16, 185, 129, 0.1)', borderRadius: 2 }}>
                      <Typography variant="caption" color="success.main">Inserted</Typography>
                      <Typography variant="h6" sx={{ fontWeight: 700, color: 'success.main' }}>{selectedLog.inserted}</Typography>
                    </Box>
                  )}
                  {selectedLog.updated != null && (
                    <Box sx={{ flex: '1 1 18%', p: 1.5, textAlign: 'center', bgcolor: 'rgba(59, 130, 246, 0.1)', borderRadius: 2 }}>
                      <Typography variant="caption" color="info.main">Updated</Typography>
                      <Typography variant="h6" sx={{ fontWeight: 700, color: 'info.main' }}>{selectedLog.updated}</Typography>
                    </Box>
                  )}
                  {selectedLog.failed != null && (
                    <Box sx={{ flex: '1 1 18%', p: 1.5, textAlign: 'center', bgcolor: 'rgba(239, 68, 68, 0.1)', borderRadius: 2 }}>
                      <Typography variant="caption" color="error.main">Failed Rows</Typography>
                      <Typography variant="h6" sx={{ fontWeight: 700, color: 'error.main' }}>{selectedLog.failed}</Typography>
                    </Box>
                  )}
                  {selectedLog.warnings != null && (
                    <Box sx={{ flex: '1 1 18%', p: 1.5, textAlign: 'center', bgcolor: 'rgba(245, 158, 11, 0.1)', borderRadius: 2 }}>
                      <Typography variant="caption" color="warning.main">Warnings</Typography>
                      <Typography variant="h6" sx={{ fontWeight: 700, color: 'warning.main' }}>{selectedLog.warnings}</Typography>
                    </Box>
                  )}
                  {selectedLog.errors != null && (
                    <Box sx={{ flex: '1 1 18%', p: 1.5, textAlign: 'center', bgcolor: 'rgba(239, 68, 68, 0.1)', borderRadius: 2 }}>
                      <Typography variant="caption" color="error.main">Errors</Typography>
                      <Typography variant="h6" sx={{ fontWeight: 700, color: 'error.main' }}>{selectedLog.errors}</Typography>
                    </Box>
                  )}
                </Stack>
              </Box>
            )}

            {/* Details string text */}
            <Box sx={{ mb: 4 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1, color: 'text.primary' }}>Logged Details</Typography>
              <Typography variant="body2" sx={{ p: 2, bgcolor: 'rgba(255,255,255,0.03)', borderRadius: 2, borderLeft: '4px solid #6366f1' }}>
                {selectedLog.details}
              </Typography>
            </Box>

            {/* Before/After states */}
            <Box>
              <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 2, color: 'text.primary' }}>Record State Modification Summary</Typography>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, md: 6 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                    <Typography variant="caption" sx={{ fontWeight: 600, color: 'primary.light' }}>Before State JSON</Typography>
                    {selectedLog.before_state && (
                      <Chip label="Original State" size="small" variant="outlined" color="primary" sx={{ fontSize: '0.65rem' }} />
                    )}
                  </Box>
                  <Box sx={{ p: 2, bgcolor: '#0b0f19', borderRadius: 2, height: 350, overflow: 'auto', border: '1px solid rgba(255,255,255,0.06)' }}>
                    <pre style={{ margin: 0, fontSize: '0.75rem', fontFamily: '"Fira Code", monospace', color: '#60a5fa', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                      {selectedLog.before_state ? JSON.stringify(selectedLog.before_state, null, 2) : '// No state captured before this operation.'}
                    </pre>
                  </Box>
                </Grid>
                <Grid size={{ xs: 12, md: 6 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                    <Typography variant="caption" sx={{ fontWeight: 600, color: 'secondary.light' }}>After State JSON</Typography>
                    {selectedLog.after_state && (
                      <Chip label="Post-Op State" size="small" variant="outlined" color="secondary" sx={{ fontSize: '0.65rem' }} />
                    )}
                  </Box>
                  <Box sx={{ p: 2, bgcolor: '#0b0f19', borderRadius: 2, height: 350, overflow: 'auto', border: '1px solid rgba(255,255,255,0.06)' }}>
                    <pre style={{ margin: 0, fontSize: '0.75rem', fontFamily: '"Fira Code", monospace', color: '#34d399', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                      {selectedLog.after_state ? JSON.stringify(selectedLog.after_state, null, 2) : '// No state captured after this operation.'}
                    </pre>
                  </Box>
                </Grid>
              </Grid>
            </Box>
          </DialogContent>

          <DialogActions sx={{ p: 3, pt: 0, borderTop: '1px solid rgba(255,255,255,0.08)' }}>
            <Button onClick={handleCloseDetails} variant="outlined" color="secondary">
              Close Details
            </Button>
          </DialogActions>
        </Dialog>
      )}
    </Box>
  );
};
