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
  ListItemText,
  Divider,
  Collapse,
  IconButton
} from '@mui/material';
import { 
  FileSpreadsheet, 
  Upload, 
  CheckCircle2, 
  AlertCircle, 
  ArrowRight,
  FileText,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  Info,
  Layers
} from 'lucide-react';
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
  const [showSynonyms, setShowSynonyms] = useState(false);

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
      const name = droppedFile.name.toLowerCase();
      if (name.endsWith('.xlsx') || name.endsWith('.xls') || name.endsWith('.pdf')) {
        setFile(droppedFile);
        setError(null);
      } else {
        setError('Invalid file type. Please upload an Excel workbook (.xlsx or .xls) or PDF invoice (.pdf).');
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      const name = selectedFile.name.toLowerCase();
      if (name.endsWith('.xlsx') || name.endsWith('.xls') || name.endsWith('.pdf')) {
        setFile(selectedFile);
        setError(null);
      } else {
        setError('Invalid file type. Please upload an Excel workbook (.xlsx or .xls) or PDF invoice (.pdf).');
      }
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
      <Grid container spacing={3} sx={{ maxWidth: 1100, mx: 'auto', mt: 2 }}>
        
        {/* Left Side: Upload Controls */}
        <Grid size={{ xs: 12, md: 7 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ p: 4 }}>
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>Ingest Trainee Invoice</Typography>
              <Typography variant="body2" sx={{ color: 'text.secondary', mb: 3 }}>
                Upload the Excel or PDF invoice file submitted by the vendor. The ingestion engine automatically matches headers using synonyms, processes visible sheets, parses kit garments, and validates against the database.
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
                title="Download Sample Excel Template"
                templatePath="/templates/Invoice_Template.xlsx"
                description="Download the official template to review the standard format containing realistic sample data."
                tooltipText="Using the official template ensures all required columns and formats are matched seamlessly."
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
                  p: 4,
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
                  accept=".xlsx, .xls, .pdf"
                  style={{ display: 'none' }}
                  onChange={handleFileChange}
                  disabled={uploading}
                />
                <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1.5 }}>
                  <Box sx={{ p: 2, borderRadius: '50%', background: 'rgba(99, 102, 241, 0.1)', color: 'primary.main' }}>
                    {file && file.name.toLowerCase().endsWith('.pdf') ? (
                      <FileText size={32} />
                    ) : (
                      <Upload size={32} />
                    )}
                  </Box>
                  <Typography variant="body1" sx={{ fontWeight: 600 }}>
                    {file ? file.name : 'Drag & drop invoice file here'}
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                    Supports Excel (.xlsx, .xls) and PDF (.pdf) up to 50MB
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
                    <span>Processing invoice rows and running validation...</span>
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
                  startIcon={file.name.toLowerCase().endsWith('.pdf') ? <FileText size={18} /> : <FileSpreadsheet size={18} />}
                  sx={{ py: 1.2, mb: 3 }}
                >
                  Parse & Ingest Invoice
                </Button>
              )}

              {/* Result Summary */}
              {result && (
                <Box sx={{ p: 2.5, borderRadius: 3, background: 'rgba(16, 185, 129, 0.06)', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
                  <Typography variant="subtitle2" sx={{ color: 'success.main', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
                    <CheckCircle2 size={18} /> Ingestion Succeeded
                  </Typography>
                  
                  <List disablePadding sx={{ mb: 2.5 }}>
                    <ListItem sx={{ py: 0.4, px: 0 }}>
                      <ListItemText 
                        primary={<Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '0.8rem' }}>Assigned Invoice Number</Typography>}
                        secondary={<Typography variant="body1" sx={{ fontWeight: 700, color: 'text.primary' }}>{result.invoice_number}</Typography>}
                      />
                    </ListItem>
                    <ListItem sx={{ py: 0.4, px: 0 }}>
                      <ListItemText 
                        primary={<Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '0.8rem' }}>Invoice Date</Typography>}
                        secondary={<Typography variant="body1" sx={{ fontWeight: 700, color: 'text.primary' }}>{result.invoice_date}</Typography>}
                      />
                    </ListItem>
                    <ListItem sx={{ py: 0.4, px: 0 }}>
                      <ListItemText 
                        primary={<Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '0.8rem' }}>Records Ingested</Typography>}
                        secondary={<Typography variant="body1" sx={{ fontWeight: 700, color: 'primary.light' }}>{result.inserted_records}</Typography>}
                      />
                    </ListItem>
                    {result.processed_sheets && result.processed_sheets.length > 0 && (
                      <ListItem sx={{ py: 0.4, px: 0 }}>
                        <ListItemText 
                          primary={<Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '0.8rem' }}>Sheets/Pages Processed</Typography>}
                          secondary={<Typography variant="body1" sx={{ fontWeight: 700, color: 'text.primary' }}>{result.processed_sheets.join(', ')}</Typography>}
                        />
                      </ListItem>
                    )}
                    {result.skipped_sheets && result.skipped_sheets.length > 0 && (
                      <ListItem sx={{ py: 0.4, px: 0 }}>
                        <ListItemText 
                          primary={<Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '0.8rem' }}>Skipped Sheets (Hidden/Empty)</Typography>}
                          secondary={<Typography variant="body1" sx={{ fontWeight: 700, color: 'warning.main' }}>{result.skipped_sheets.join(', ')}</Typography>}
                        />
                      </ListItem>
                    )}
                  </List>

                  {(result.errors && result.errors.length > 0) && (
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="caption" sx={{ color: 'error.main', fontWeight: 600, display: 'block', mb: 0.5 }}>Ingestion Warnings/Errors ({result.errors.length}):</Typography>
                      <Box sx={{ maxHeight: 120, overflowY: 'auto', p: 1, borderRadius: 1.5, background: 'rgba(239, 68, 68, 0.05)', border: '1px solid rgba(239, 68, 68, 0.1)' }}>
                        {result.errors.map((err: string, i: number) => (
                          <Typography key={i} variant="caption" sx={{ display: 'block', color: 'error.light', mb: 0.5 }}>• {err}</Typography>
                        ))}
                      </Box>
                    </Box>
                  )}

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
        </Grid>

        {/* Right Side: Accepted Formats & Specifications */}
        <Grid size={{ xs: 12, md: 5 }}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, height: '100%' }}>
            
            {/* Accepted Formats panel */}
            <Card>
              <CardContent sx={{ p: 3 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Layers size={18} className="text-secondary" /> Accepted Formats
                </Typography>
                <Grid container spacing={2}>
                  <Grid size={{ xs: 6 }}>
                    <Box sx={{ p: 2, borderRadius: 2, background: 'rgba(255,255,255,0.02)', textAlign: 'center', border: '1px solid rgba(255,255,255,0.05)' }}>
                      <FileSpreadsheet size={24} className="text-success" style={{ marginBottom: 4 }} />
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>Excel Workbook</Typography>
                      <Typography variant="caption" sx={{ color: 'text.secondary' }}>.xlsx, .xls</Typography>
                    </Box>
                  </Grid>
                  <Grid size={{ xs: 6 }}>
                    <Box sx={{ p: 2, borderRadius: 2, background: 'rgba(255,255,255,0.02)', textAlign: 'center', border: '1px solid rgba(255,255,255,0.05)' }}>
                      <FileText size={24} className="text-danger" style={{ marginBottom: 4 }} />
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>PDF Document</Typography>
                      <Typography variant="caption" sx={{ color: 'text.secondary' }}>.pdf (tabular)</Typography>
                    </Box>
                  </Grid>
                </Grid>
              </CardContent>
            </Card>

            {/* Required Columns panel */}
            <Card>
              <CardContent sx={{ p: 3 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Info size={18} className="text-primary" /> Specifications & Columns
                </Typography>
                <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>
                  The ingestion layer looks for these business fields. Extra columns are ignored unless explicitly mapped.
                </Typography>
                
                <Grid container spacing={1}>
                  {[
                    { col: 'Sr no', status: 'Required' },
                    { col: 'T No', status: 'Required' },
                    { col: 'Date Of Joining', status: 'Required' },
                    { col: 'Batch No', status: 'Required' },
                    { col: 'Candidates Name', status: 'Required' },
                    { col: 'Pair', status: 'Required' },
                    { col: 'Amount', status: 'Required' },
                    { col: 'Distribution Date', status: 'Required' },
                    { col: 'Page No', status: 'Optional' }
                  ].map((item, idx) => (
                    <Grid size={{ xs: 6 }} key={idx}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', p: 1, px: 1.5, borderRadius: 1.5, background: 'rgba(255,255,255,0.01)', border: '1px solid rgba(255,255,255,0.03)' }}>
                        <Typography variant="body2" sx={{ fontSize: '0.8rem', fontWeight: 500 }}>{item.col}</Typography>
                        <Typography variant="caption" sx={{ fontSize: '0.7rem', color: item.status === 'Required' ? 'primary.light' : 'text.secondary' }}>
                          {item.status}
                        </Typography>
                      </Box>
                    </Grid>
                  ))}
                </Grid>
              </CardContent>
            </Card>

            {/* Synonym Preview Accordion */}
            <Card>
              <CardContent sx={{ p: 2.5 }}>
                <Box 
                  onClick={() => setShowSynonyms(!showSynonyms)}
                  sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
                >
                  <Typography variant="subtitle1" sx={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: 1 }}>
                    <HelpCircle size={18} /> Synonym Dictionary
                  </Typography>
                  <IconButton size="small">
                    {showSynonyms ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </IconButton>
                </Box>
                
                <Collapse in={showSynonyms} timeout="auto" unmountOnExit>
                  <Box sx={{ mt: 2 }}>
                    <Divider sx={{ mb: 1.5 }} />
                    <List disablePadding>
                      {[
                        { title: 'T No', syns: 'T No, Ticket No, Ticket Number, Pers No, Boarding Ticket' },
                        { title: 'Date Of Joining', syns: 'Date Of Joining, Joining Date, DOJ, Begda' },
                        { title: 'Candidates Name', syns: 'Candidates Name, Employee Name, Name, Fullname' },
                        { title: 'Pair', syns: 'Pair, Uniform Pair, Kit Pair' },
                        { title: 'Amount', syns: 'Amount, Bill Amount, Billing Amount, Claimed Amount' },
                        { title: 'Distribution Date', syns: 'Distribution Date, Issued Date' },
                        { title: 'Page No', syns: 'Page No, Page' }
                      ].map((item, idx) => (
                        <Box key={idx} sx={{ mb: 1.2 }}>
                          <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.8rem', color: 'primary.light' }}>
                            {item.title}
                          </Typography>
                          <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 0.2 }}>
                            {item.syns}
                          </Typography>
                        </Box>
                      ))}
                    </List>
                  </Box>
                </Collapse>
              </CardContent>
            </Card>
            
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
};
