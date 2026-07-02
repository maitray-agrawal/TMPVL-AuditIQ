import React, { useState } from 'react';
import { 
  Box, 
  Card, 
  CardContent, 
  Typography, 
  Button, 
  LinearProgress, 
  Alert,
  List,
  ListItem,
  ListItemText,
  Grid
} from '@mui/material';
import { FileSpreadsheet, Upload, CheckCircle2, AlertCircle } from 'lucide-react';
import api from '../api';
import { DownloadTemplateButton } from '../components/DownloadTemplateButton';

export const SeparationUpload: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
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

      const res = await api.post('/uploads/separation', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setResult(res.data);
      setFile(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'An error occurred while uploading the Separation workbook.');
    } finally {
      setUploading(false);
    }
  };

  return (
    <Box className="fade-in-section">
      <Card sx={{ maxWidth: 650, mx: 'auto', mt: 4 }}>
        <CardContent sx={{ p: 4 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>Separation Records Ingestion</Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', mb: 3 }}>
            Upload the Separation Master workbook to sync trainee Dates of Leaving (DOL) and update active status to SEPARATED.
          </Typography>

          {/* Download Template Button */}
          <DownloadTemplateButton
            title="Download Sample Template"
            templatePath="/templates/Separation_Template.xlsx"
            description="Download the official template, fill your separation data, then upload it back. Contains monthly separation sample sheets for NAPS, BTECH and MTECH."
            tooltipText="Using the official template ensures all required columns and sheet names match the validation engine."
          />

          {/* Drag & Drop Area */}
          <Box
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            sx={{
              border: '2px dashed',
              borderColor: isDragOver ? 'secondary.main' : 'rgba(255,255,255,0.15)',
              borderRadius: 3,
              p: 5,
              textAlign: 'center',
              cursor: 'pointer',
              background: isDragOver ? 'rgba(6, 182, 212, 0.05)' : 'rgba(255, 255, 255, 0.01)',
              transition: 'all 0.2s ease-in-out',
              '&:hover': {
                borderColor: 'secondary.light',
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
              <Box sx={{ p: 2, borderRadius: '50%', background: 'rgba(6, 182, 212, 0.1)', color: 'secondary.main' }}>
                <Upload size={32} />
              </Box>
              <Typography variant="body1" sx={{ fontWeight: 600 }}>
                {file ? file.name : 'Drag & drop your Separation file here'}
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
                <span>Parsing resignation dates and separating profiles...</span>
                <span>Please wait</span>
              </Typography>
              <LinearProgress color="secondary" />
            </Box>
          )}

          {file && !uploading && (
            <Button
              fullWidth
              variant="contained"
              color="secondary"
              onClick={handleUpload}
              startIcon={<FileSpreadsheet size={18} />}
              sx={{ py: 1.2, mb: 3 }}
            >
              Parse & Sync Separations
            </Button>
          )}

          {/* Result Block */}
          {result && (
            <Box 
              sx={{ 
                p: 3, 
                borderRadius: 4, 
                background: 'rgba(255, 255, 255, 0.02)', 
                backdropFilter: 'blur(10px)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                boxShadow: '0 8px 32px 0 rgba(0, 0, 0, 0.3)',
                mt: 3
              }}
            >
              <Typography variant="subtitle1" sx={{ color: '#06b6d4', fontWeight: 800, display: 'flex', alignItems: 'center', gap: 1, mb: 2.5 }}>
                <CheckCircle2 size={20} /> Ingestion Summary
              </Typography>
              
              <Grid container spacing={2} sx={{ mb: 3 }}>
                <Grid size={{ xs: 6, sm: 4 }}>
                  <Box sx={{ p: 1.5, borderRadius: 2.5, background: 'rgba(255, 255, 255, 0.01)', border: '1px solid rgba(255, 255, 255, 0.04)', textAlign: 'center' }}>
                    <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 0.5 }}>SHEETS PROCESSED</Typography>
                    <Typography variant="body1" sx={{ fontWeight: 800, color: '#fff' }}>{result.sheets_processed?.length || 0}</Typography>
                  </Box>
                </Grid>
                <Grid size={{ xs: 6, sm: 4 }}>
                  <Box sx={{ p: 1.5, borderRadius: 2.5, background: 'rgba(255, 255, 255, 0.01)', border: '1px solid rgba(255, 255, 255, 0.04)', textAlign: 'center' }}>
                    <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 0.5 }}>EMPLOYEES UPDATED</Typography>
                    <Typography variant="body1" sx={{ fontWeight: 800, color: 'success.main' }}>{result.employees_updated}</Typography>
                  </Box>
                </Grid>
                <Grid size={{ xs: 6, sm: 4 }}>
                  <Box sx={{ p: 1.5, borderRadius: 2.5, background: 'rgba(255, 255, 255, 0.01)', border: '1px solid rgba(255, 255, 255, 0.04)', textAlign: 'center' }}>
                    <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 0.5 }}>EARLY SEPARATIONS</Typography>
                    <Typography variant="body1" sx={{ fontWeight: 800, color: '#f59e0b' }}>{result.early_separations}</Typography>
                  </Box>
                </Grid>
                <Grid size={{ xs: 6, sm: 4 }}>
                  <Box sx={{ p: 1.5, borderRadius: 2.5, background: 'rgba(255, 255, 255, 0.01)', border: '1px solid rgba(255, 255, 255, 0.04)', textAlign: 'center' }}>
                    <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 0.5 }}>BLOCKED</Typography>
                    <Typography variant="body1" sx={{ fontWeight: 800, color: 'error.main' }}>{result.blocked_employees}</Typography>
                  </Box>
                </Grid>
                <Grid size={{ xs: 6, sm: 4 }}>
                  <Box sx={{ p: 1.5, borderRadius: 2.5, background: 'rgba(255, 255, 255, 0.01)', border: '1px solid rgba(255, 255, 255, 0.04)', textAlign: 'center' }}>
                    <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 0.5 }}>SEPARATED</Typography>
                    <Typography variant="body1" sx={{ fontWeight: 800, color: 'secondary.light' }}>{result.separated}</Typography>
                  </Box>
                </Grid>
                <Grid size={{ xs: 6, sm: 4 }}>
                  <Box sx={{ p: 1.5, borderRadius: 2.5, background: 'rgba(255, 255, 255, 0.01)', border: '1px solid rgba(255, 255, 255, 0.04)', textAlign: 'center' }}>
                    <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 0.5 }}>DUPLICATES</Typography>
                    <Typography variant="body1" sx={{ fontWeight: 800, color: 'text.secondary' }}>{result.duplicates}</Typography>
                  </Box>
                </Grid>
                <Grid size={{ xs: 6, sm: 4 }}>
                  <Box sx={{ p: 1.5, borderRadius: 2.5, background: 'rgba(255, 255, 255, 0.01)', border: '1px solid rgba(255, 255, 255, 0.04)', textAlign: 'center' }}>
                    <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 0.5 }}>UNKNOWN EMPLOYEES</Typography>
                    <Typography variant="body1" sx={{ fontWeight: 800, color: 'error.light' }}>{result.unknown_employees}</Typography>
                  </Box>
                </Grid>
              </Grid>

              {result.warnings && result.warnings.length > 0 && (
                <Box sx={{ mb: 2, p: 2, borderRadius: 3, background: 'rgba(245, 158, 11, 0.06)', border: '1px solid rgba(245, 158, 11, 0.2)' }}>
                  <Typography variant="body2" sx={{ fontWeight: 700, color: '#f59e0b', mb: 1 }}>Warnings:</Typography>
                  <List disablePadding>
                    {result.warnings.map((w: string, idx: number) => (
                      <ListItem key={idx} sx={{ py: 0.25, px: 0 }}>
                        <ListItemText primary={<Typography variant="body2" sx={{ fontSize: '0.8rem' }}>{w}</Typography>} />
                      </ListItem>
                    ))}
                  </List>
                </Box>
              )}

              {result.errors && result.errors.length > 0 && (
                <Box sx={{ p: 2, borderRadius: 3, background: 'rgba(239, 68, 68, 0.06)', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
                  <Typography variant="body2" sx={{ fontWeight: 700, color: 'error.main', mb: 1 }}>Errors:</Typography>
                  <List disablePadding>
                    {result.errors.map((e: string, idx: number) => (
                      <ListItem key={idx} sx={{ py: 0.25, px: 0 }}>
                        <ListItemText primary={<Typography variant="body2" sx={{ fontSize: '0.8rem' }}>{e}</Typography>} />
                      </ListItem>
                    ))}
                  </List>
                </Box>
              )}
            </Box>
          )}
        </CardContent>
      </Card>
    </Box>
  );
};
