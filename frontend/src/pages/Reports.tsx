import React, { useEffect, useState } from 'react';
import { 
  Box, 
  Card, 
  CardContent, 
  Typography, 
  Button, 
  Grid, 
  MenuItem, 
  TextField 
} from '@mui/material';
import { 
  FileSpreadsheet, 
  ShieldAlert, 
  TrendingUp, 
  FileText, 
  History 
} from 'lucide-react';
import api from '../api';

interface InvoiceSummary {
  invoice_number: string;
  status: string;
}

export const Reports: React.FC = () => {
  const [invoices, setInvoices] = useState<InvoiceSummary[]>([]);
  const [selectedInvoiceNumber, setSelectedInvoiceNumber] = useState('');
  const [selectedExceptionInvoice, setSelectedExceptionInvoice] = useState('');

  useEffect(() => {
    const fetchInvoices = async () => {
      try {
        const res = await api.get('/invoices');
        setInvoices(res.data);
        const approvedOnly = res.data.filter((i: any) => i.status === 'APPROVED');
        if (approvedOnly.length > 0) {
          setSelectedInvoiceNumber(approvedOnly[0].invoice_number);
        } else if (res.data.length > 0) {
          setSelectedInvoiceNumber(res.data[0].invoice_number);
        }
      } catch (err) {
        console.error("Failed to load invoices for reports", err);
      }
    };
    fetchInvoices();
  }, []);

  const handleDownload = (endpoint: string) => {
    window.location.href = `http://127.0.0.1:8000/api${endpoint}`;
  };

  return (
    <Box className="fade-in-section">
      <Typography variant="body2" sx={{ color: 'text.secondary', mb: 4 }}>
        Download official Microsoft Excel spreadsheets for system audit tracking, finance reconciliation, and compliance reporting.
      </Typography>

      <Grid container spacing={3}>
        {/* Approved Payouts */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <CardContent sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
                <Box sx={{ p: 1.5, borderRadius: 2, background: 'rgba(16, 185, 129, 0.1)', color: 'success.main' }}>
                  <TrendingUp size={24} />
                </Box>
                <Typography variant="h6" sx={{ fontWeight: 700 }}>Approved Payouts Sheet</Typography>
              </Box>
              
              <Typography variant="body2" sx={{ color: 'text.secondary', mb: 3 }}>
                Exports a list of all verified and approved trainee payouts for the selected monthly billing cycle. Contains only items with approved payout amounts &gt; 0.
              </Typography>

              {invoices.length > 0 && (
                <TextField
                  select
                  fullWidth
                  size="small"
                  label="Select Approved Invoice"
                  value={selectedInvoiceNumber}
                  onChange={(e) => setSelectedInvoiceNumber(e.target.value)}
                  sx={{ mb: 2 }}
                >
                  {invoices.map((inv) => (
                    <MenuItem key={inv.invoice_number} value={inv.invoice_number}>
                      {inv.invoice_number} ({inv.status})
                    </MenuItem>
                  ))}
                </TextField>
              )}
            </CardContent>
            <Box sx={{ p: 3, pt: 0 }}>
              <Button
                fullWidth
                variant="contained"
                color="success"
                startIcon={<FileSpreadsheet size={18} />}
                disabled={!selectedInvoiceNumber}
                onClick={() => handleDownload(`/reports/approved-invoice/${selectedInvoiceNumber}`)}
              >
                Download Approved Invoice
              </Button>
            </Box>
          </Card>
        </Grid>

        {/* Exceptions & Warnings */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <CardContent sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
                <Box sx={{ p: 1.5, borderRadius: 2, background: 'rgba(245, 158, 11, 0.1)', color: 'warning.main' }}>
                  <ShieldAlert size={24} />
                </Box>
                <Typography variant="h6" sx={{ fontWeight: 700 }}>Audit Exception Report</Typography>
              </Box>
              
              <Typography variant="body2" sx={{ color: 'text.secondary', mb: 3 }}>
                Exports all warnings, missing documents, or policy cap violations. Choose a specific invoice cycle or export all historical alerts.
              </Typography>

              <TextField
                select
                fullWidth
                size="small"
                label="Select Invoice (Optional)"
                value={selectedExceptionInvoice}
                onChange={(e) => setSelectedExceptionInvoice(e.target.value)}
                sx={{ mb: 2 }}
              >
                <MenuItem value="">All Historical Invoices</MenuItem>
                {invoices.map((inv) => (
                  <MenuItem key={inv.invoice_number} value={inv.invoice_number}>
                    {inv.invoice_number}
                  </MenuItem>
                ))}
              </TextField>
            </CardContent>
            <Box sx={{ p: 3, pt: 0 }}>
              <Button
                fullWidth
                variant="contained"
                color="primary"
                startIcon={<FileSpreadsheet size={18} />}
                onClick={() => handleDownload(`/reports/exceptions${selectedExceptionInvoice ? `?invoice_number=${selectedExceptionInvoice}` : ''}`)}
              >
                Download Exception Report
              </Button>
            </Box>
          </Card>
        </Grid>

        {/* Fraud Incidents */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <CardContent sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
                <Box sx={{ p: 1.5, borderRadius: 2, background: 'rgba(239, 68, 68, 0.1)', color: 'error.main' }}>
                  <ShieldAlert size={24} />
                </Box>
                <Typography variant="h6" sx={{ fontWeight: 700 }}>Fraud Incidents Report</Typography>
              </Box>
              
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                Exports all database events categorized as FRAUD or critical violations, including double claiming and blocked list hits.
              </Typography>
            </CardContent>
            <Box sx={{ p: 3 }}>
              <Button
                fullWidth
                variant="outlined"
                color="error"
                startIcon={<FileSpreadsheet size={18} />}
                onClick={() => handleDownload('/reports/fraud')}
              >
                Download Fraud Report
              </Button>
            </Box>
          </Card>
        </Grid>

        {/* Payment Ledger Summary */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <CardContent sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
                <Box sx={{ p: 1.5, borderRadius: 2, background: 'rgba(99, 102, 241, 0.1)', color: 'primary.main' }}>
                  <FileText size={24} />
                </Box>
                <Typography variant="h6" sx={{ fontWeight: 700 }}>Trainee Ledger Summary</Typography>
              </Box>
              
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                Generates a master sheet of all trainees, showing their lifetime disbursements (joining and 180-days paid sums) and remaining caps.
              </Typography>
            </CardContent>
            <Box sx={{ p: 3 }}>
              <Button
                fullWidth
                variant="outlined"
                color="primary"
                startIcon={<FileSpreadsheet size={18} />}
                onClick={() => handleDownload('/reports/payment-summary')}
              >
                Download Ledger Summary
              </Button>
            </Box>
          </Card>
        </Grid>

        {/* System Audit Trail */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <CardContent sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
                <Box sx={{ p: 1.5, borderRadius: 2, background: 'rgba(255, 255, 255, 0.05)', color: '#fff' }}>
                  <History size={24} />
                </Box>
                <Typography variant="h6" sx={{ fontWeight: 700 }}>System Audit Logs</Typography>
              </Box>
              
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                Generates a complete log of administrative actions, workbook imports, validations, and modifications for IT compliance.
              </Typography>
            </CardContent>
            <Box sx={{ p: 3 }}>
              <Button
                fullWidth
                variant="outlined"
                color="inherit"
                startIcon={<FileSpreadsheet size={18} />}
                onClick={() => handleDownload('/reports/audit-logs')}
              >
                Download System Audit
              </Button>
            </Box>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};
