import React, { useState } from 'react';
import { 
  Box, 
  Card, 
  CardContent, 
  Typography, 
  Button, 
  LinearProgress, 
  Alert,
  TextField,
  Grid,
  List,
  ListItem,
  ListItemText
} from '@mui/material';
import { FileSpreadsheet, Upload, CheckCircle2, AlertCircle, ArrowRight } from 'lucide-react';
import api from '../api';
import { DownloadTemplateButton } from '../components/DownloadTemplateButton';

interface InvoiceUploadProps {
  onPageChange: (page: string) => void;
}

export const InvoiceUpload: React.FC<InvoiceUploadProps> = ({ onPageChange }) => {
  const [file, setFile] = useState<File | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  
  // Overrides
  const [invoiceNumber, setInvoiceNumber] = useState('');
  const [invoiceDate, setInvoiceDate] = useState('');

  const [result, setResult] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile.name.endsWith('.xlsx') || droppedFile.name.endsWith('.xls')) {
        setFile(droppedFile);
        setError(null);
      } else {
        setError('Invalid file type. Please upload an Excel workbook (.xlsx or .xls).');
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    try {
      setUploading(true);
      setError(null);
      setResult(null);

      const formData = new FormData();
      formData.append('file', file);
      if (invoiceNumber) {
        formData.append('invoice_number', invoiceNumber);
      }
      if (invoiceDate) {
        formData.append('invoice_date', invoiceDate);
      }

      const res = await api.post('/uploads/invoice', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setResult(res.data);
      setFile(null);
      setInvoiceNumber('');
      setInvoiceDate('');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'An error occurred while uploading the invoice.');
    } finally {
      setUploading(false);
    }
  };

  return (
    <Box className="fade-in-section">
      <Card sx={{ maxWidth: 650, mx: 'auto', mt: 2 }}>
        <CardContent sx={{ p: 4 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>Ingest Monthly Trainee Billing Invoice</Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', mb: 3 }}>
            Upload the raw Excel invoice file submitted by the vendor. The system will auto-extract trainee IDs, names, billed amounts, and dates.
          </Typography>

          {/* Overrides Input */}
          <Grid container spacing={2} sx={{ mb: 3 }}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                fullWidth
                size="small"
                label="Invoice Number Override (Optional)"
                placeholder="e.g. QIPL/2026/04"
                value={invoiceNumber}
                onChange={(e) => setInvoiceNumber(e.target.value)}
                disabled={uploading}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                fullWidth
                size="small"
                label="Invoice Date Override (Optional)"
                type="date"
                slotProps={{
                  inputLabel: {
                    shrink: true
                  }
                }}
                value={invoiceDate}
                onChange={(e) => setInvoiceDate(e.target.value)}
                disabled={uploading}
              />
            </Grid>
          </Grid>

          {/* Download Template Button */}
          <DownloadTemplateButton
            title="Download Sample Template"
            templatePath="/templates/Invoice_Template.xlsx"
            description="Download the official template, fill your invoice data, then upload it back. Contains sample invoice format with valid and fraud example rows."
            tooltipText="Using the official template ensures all required columns and sheet names match the validation engine."
          />

          {/* Drag & Drop Area */}
          <Box
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            sx={{
              border: '2px dashed',
              borderColor: isDragOver ? 'primary.main' : 'rgba(255,255,255,0.15)',
              borderRadius: 3,
              p: 5,
              textAlign: 'center',
              cursor: 'pointer',
              background: isDragOver ? 'rgba(99, 102, 241, 0.05)' : 'rgba(255, 255, 255, 0.01)',
              transition: 'all 0.2s ease-in-out',
              '&:hover': {
                borderColor: 'primary.light',
                background: 'rgba(255, 255, 255, 0.02)',
              },
              mb: 3,
            }}
            component="label"
          >
            <input
              type="file"
              accept=".xlsx, .xls"
              style={{ display: 'none' }}
              onChange={handleFileChange}
              disabled={uploading}
            />
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1.5 }}>
              <Box sx={{ p: 2, borderRadius: '50%', background: 'rgba(99, 102, 241, 0.1)', color: 'primary.main' }}>
                <Upload size={32} />
              </Box>
              <Typography variant="body1" sx={{ fontWeight: 600 }}>
                {file ? file.name : 'Drag & drop your Invoice file here'}
              </Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                Supports Excel Workbooks (.xlsx, .xls) up to 25MB
              </Typography>
            </Box>
          </Box>

          {error && (
            <Alert severity="error" icon={<AlertCircle size={20} />} sx={{ mb: 3, borderRadius: 2 }}>
              {error}
            </Alert>
          )}

          {uploading && (
            <Box sx={{ width: '100%', mb: 3 }}>
              <Typography variant="body2" sx={{ mb: 1, color: 'text.secondary', display: 'flex', justifyContent: 'space-between' }}>
                <span>Processing vendor invoice rows...</span>
                <span>Please wait</span>
              </Typography>
              <LinearProgress color="primary" />
            </Box>
          )}

          {file && !uploading && (
            <Button
              fullWidth
              variant="contained"
              color="primary"
              onClick={handleUpload}
              startIcon={<FileSpreadsheet size={18} />}
              sx={{ py: 1.2, mb: 3 }}
            >
              Parse & Save Invoice
            </Button>
          )}

          {/* Result Block */}
          {result && (
            <Box sx={{ p: 2.5, borderRadius: 3, background: 'rgba(16, 185, 129, 0.06)', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
              <Typography variant="subtitle2" sx={{ color: 'success.main', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
                <CheckCircle2 size={18} /> Ingestion Succeeded
              </Typography>
              
              <List disablePadding sx={{ mb: 2.5 }}>
                <ListItem sx={{ py: 0.5, px: 0 }}>
                  <ListItemText 
                    primary={
                      <Typography variant="body2" sx={{ fontSize: '0.85rem', color: 'text.secondary' }}>
                        Assigned Invoice Number
                      </Typography>
                    }
                    secondary={
                      <Typography variant="body1" sx={{ fontSize: '1rem', fontWeight: 700, color: 'text.primary' }}>
                        {result.invoice_number}
                      </Typography>
                    }
                  />
                </ListItem>
                <ListItem sx={{ py: 0.5, px: 0 }}>
                  <ListItemText 
                    primary={
                      <Typography variant="body2" sx={{ fontSize: '0.85rem', color: 'text.secondary' }}>
                        Extracted Invoice Date
                      </Typography>
                    }
                    secondary={
                      <Typography variant="body1" sx={{ fontSize: '1rem', fontWeight: 700, color: 'text.primary' }}>
                        {result.invoice_date}
                      </Typography>
                    }
                  />
                </ListItem>
                <ListItem sx={{ py: 0.5, px: 0 }}>
                  <ListItemText 
                    primary={
                      <Typography variant="body2" sx={{ fontSize: '0.85rem', color: 'text.secondary' }}>
                        Total Trainee Records Ingested
                      </Typography>
                    }
                    secondary={
                      <Typography variant="body1" sx={{ fontSize: '1rem', fontWeight: 700, color: 'primary.light' }}>
                        {result.records_imported}
                      </Typography>
                    }
                  />
                </ListItem>
              </List>

              <Button
                fullWidth
                variant="contained"
                color="success"
                onClick={() => onPageChange('validation')}
                endIcon={<ArrowRight size={16} />}
              >
                Go to Validation Engine
              </Button>
            </Box>
          )}
        </CardContent>
      </Card>
    </Box>
  );
};
