import React, { useState } from 'react';
import { 
  Box, 
  Card, 
  CardContent, 
  Typography, 
  Button, 
  LinearProgress, 
  Alert,
  Grid,
  Divider,
  Paper
} from '@mui/material';
import { FileSpreadsheet, Upload, CheckCircle2, AlertCircle, Sparkles, Check } from 'lucide-react';
import api from '../api';
import { DownloadTemplateButton } from '../components/DownloadTemplateButton';

interface UploadCardProps {
  title: string;
  recommended?: boolean;
  templatePath: string;
  description: string;
  tooltipText: string;
  uploadUrl: string;
  uploadMode: string;
  color: 'primary' | 'secondary';
  noteText?: string;
}

const UploadCard: React.FC<UploadCardProps> = ({
  title,
  recommended = false,
  templatePath,
  description,
  tooltipText,
  uploadUrl,
  uploadMode,
  color,
  noteText
}) => {
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
      formData.append('upload_mode', uploadMode);

      const res = await api.post(uploadUrl, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setResult(res.data);
      setFile(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || `An error occurred while uploading ${title}.`);
    } finally {
      setUploading(false);
    }
  };

  const primaryColor = color === 'primary' ? 'rgba(99, 102, 241, 1)' : 'rgba(6, 182, 212, 1)';
  const glowShadow = color === 'primary' 
    ? '0 0 20px rgba(99, 102, 241, 0.15), inset 0 0 10px rgba(99, 102, 241, 0.05)' 
    : '0 0 20px rgba(6, 182, 212, 0.15), inset 0 0 10px rgba(6, 182, 212, 0.05)';

  return (
    <Card 
      sx={{ 
        position: 'relative',
        height: '100%',
        border: recommended ? `2px solid ${primaryColor}` : '1px solid rgba(255,255,255,0.06)',
        background: recommended 
          ? `linear-gradient(135deg, ${color === 'primary' ? 'rgba(99, 102, 241, 0.03)' : 'rgba(6, 182, 212, 0.03)'} 0%, rgba(255, 255, 255, 0.01) 100%)`
          : 'rgba(255, 255, 255, 0.01)',
        boxShadow: recommended ? glowShadow : 'none',
        transition: 'all 0.3s ease-in-out',
        '&:hover': {
          boxShadow: recommended ? glowShadow : '0 8px 24px rgba(0,0,0,0.2)',
          borderColor: primaryColor,
        }
      }}
    >
      {recommended && (
        <Box sx={{
          position: 'absolute',
          top: 16,
          right: 16,
          background: color === 'primary' ? 'rgba(99, 102, 241, 0.15)' : 'rgba(6, 182, 212, 0.15)',
          color: color === 'primary' ? 'primary.light' : 'secondary.light',
          fontSize: '0.72rem',
          fontWeight: 800,
          px: 1.5,
          py: 0.5,
          borderRadius: 1,
          border: `1px solid ${primaryColor}`,
          display: 'flex',
          alignItems: 'center',
          gap: 0.5,
          letterSpacing: '0.05em'
        }}>
          <Sparkles size={12} /> RECOMMENDED
        </Box>
      )}

      <CardContent sx={{ p: recommended ? 4 : 3 }}>
        <Typography variant="h6" sx={{ fontWeight: 800, mb: 1, pr: recommended ? 15 : 0 }}>
          {title}
        </Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary', mb: 3 }}>
          {noteText}
        </Typography>

        <Divider sx={{ my: 2.5, borderColor: 'rgba(255,255,255,0.06)' }} />

        {/* Download Sample */}
        <DownloadTemplateButton
          title="Download Sample Template"
          templatePath={templatePath}
          description={description}
          tooltipText={tooltipText}
        />

        {/* Drag & Drop Area */}
        <Box
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          sx={{
            border: '2px dashed',
            borderColor: isDragOver ? primaryColor : 'rgba(255,255,255,0.12)',
            borderRadius: 3,
            p: recommended ? 4 : 3,
            textAlign: 'center',
            cursor: 'pointer',
            background: isDragOver 
              ? (color === 'primary' ? 'rgba(99, 102, 241, 0.05)' : 'rgba(6, 182, 212, 0.05)') 
              : 'rgba(255, 255, 255, 0.01)',
            transition: 'all 0.2s ease-in-out',
            '&:hover': {
              borderColor: primaryColor,
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
            <Box sx={{ 
              p: 2, 
              borderRadius: '50%', 
              background: color === 'primary' ? 'rgba(99, 102, 241, 0.1)' : 'rgba(6, 182, 212, 0.1)', 
              color: primaryColor 
            }}>
              <Upload size={28} />
            </Box>
            <Typography variant="body2" sx={{ fontWeight: 600, color: file ? 'text.primary' : 'text.secondary' }}>
              {file ? file.name : 'Drag & drop Excel file here or Browse'}
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.72rem' }}>
              Excel Workbooks (.xlsx, .xls) up to 25MB
            </Typography>
          </Box>
        </Box>

        {error && (
          <Alert severity="error" icon={<AlertCircle size={18} />} sx={{ mb: 3, borderRadius: 2 }}>
            {error}
          </Alert>
        )}

        {uploading && (
          <Box sx={{ width: '100%', mb: 3 }}>
            <Typography variant="caption" sx={{ mb: 0.8, color: 'text.secondary', display: 'flex', justifyContent: 'space-between' }}>
              <span>Parsing resignation dates and separating profiles...</span>
              <span>Please wait</span>
            </Typography>
            <LinearProgress color={color} />
          </Box>
        )}

        {file && !uploading && (
          <Button
            fullWidth
            variant="contained"
            color={color}
            onClick={handleUpload}
            startIcon={<FileSpreadsheet size={16} />}
            sx={{ py: recommended ? 1.2 : 1, mb: 3, fontWeight: 700 }}
          >
            Parse & Sync Separations
          </Button>
        )}

        {/* Result Block */}
        {result && (
          <Paper 
            variant="outlined"
            sx={{ 
              p: 2.5, 
              borderRadius: 3, 
              background: 'rgba(255, 255, 255, 0.01)', 
              borderColor: result.errors && result.errors.length > 0 ? 'rgba(239, 68, 68, 0.2)' : 'rgba(6, 182, 212, 0.2)'
            }}
          >
            <Typography 
              variant="subtitle2" 
              sx={{ 
                color: result.errors && result.errors.length > 0 ? 'error.main' : '#06b6d4', 
                fontWeight: 800, 
                display: 'flex', 
                alignItems: 'center', 
                gap: 0.8, 
                mb: 2 
              }}
            >
              {result.errors && result.errors.length > 0 ? (
                <>
                  <AlertCircle size={18} /> Ingestion Completed with Warnings
                </>
              ) : (
                <>
                  <CheckCircle2 size={18} /> Ingestion Succeeded
                </>
              )}
            </Typography>

            {/* Quick stats grid */}
            <Grid container spacing={1.5} sx={{ mb: 2 }}>
              {[
                { label: 'Rows Read', val: result.rows_processed || result.total_records, color: 'text.primary' },
                { label: 'Updated', val: result.employees_updated ?? (result.inserted_records || result.success_count), color: 'success.main' },
                { label: 'Early Exits', val: result.early_separations, color: 'warning.main' },
                { label: 'Blocked', val: result.blocked_employees, color: 'error.main' }
              ].map((stat, idx) => (
                <Grid size={{ xs: 6, sm: 3 }} key={idx}>
                  <Box sx={{ 
                    p: 1, 
                    borderRadius: 2, 
                    background: 'rgba(255, 255, 255, 0.01)', 
                    border: '1px solid rgba(255, 255, 255, 0.03)', 
                    textAlign: 'center' 
                  }}>
                    <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', fontSize: '0.65rem' }}>
                      {stat.label.toUpperCase()}
                    </Typography>
                    <Typography variant="body2" sx={{ fontWeight: 800, color: stat.color }}>
                      {stat.val ?? 0}
                    </Typography>
                  </Box>
                </Grid>
              ))}
            </Grid>

            {/* Sheet-wise summaries */}
            {result.sheet_summaries && result.sheet_summaries.length > 0 && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary', display: 'block', mb: 1 }}>
                  SHEETS PROCESSED:
                </Typography>
                <Grid container spacing={1}>
                  {result.sheet_summaries.map((s: any, idx: number) => (
                    <Grid size={{ xs: 12 }} key={idx}>
                      <Box sx={{ 
                        p: 1.2, 
                        borderRadius: 2, 
                        background: 'rgba(255,255,255,0.01)', 
                        border: '1px solid rgba(255,255,255,0.04)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between'
                      }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Check size={14} className="text-success" />
                          <Box>
                            <Typography variant="body2" sx={{ fontWeight: 700, fontSize: '0.8rem' }}>
                              {s.sheet_name}
                            </Typography>
                            <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.68rem', display: 'block' }}>
                              Scheme: {s.scheme} | Type: {s.sheet_type}
                            </Typography>
                          </Box>
                        </Box>
                        <Typography variant="caption" sx={{ color: 'text.primary', fontSize: '0.72rem', fontWeight: 600 }}>
                          Read: {s.rows_read} | Upd: {s.updated} | Skip: {s.skipped}
                        </Typography>
                      </Box>
                    </Grid>
                  ))}
                </Grid>
              </Box>
            )}

            {/* Warnings log */}
            {result.warnings && result.warnings.length > 0 && (
              <Box sx={{ mb: 1.5 }}>
                <Typography variant="caption" sx={{ color: 'warning.main', fontWeight: 700, display: 'block', mb: 0.5 }}>
                  Warnings ({result.warnings.length}):
                </Typography>
                <Box sx={{ 
                  maxHeight: 100, 
                  overflowY: 'auto', 
                  p: 1, 
                  borderRadius: 2, 
                  background: 'rgba(245, 158, 11, 0.03)', 
                  border: '1px solid rgba(245, 158, 11, 0.1)' 
                }}>
                  {result.warnings.map((w: string, idx: number) => (
                    <Typography key={idx} variant="caption" sx={{ display: 'block', color: 'warning.light', mb: 0.4, fontSize: '0.72rem' }}>
                      • {w}
                    </Typography>
                  ))}
                </Box>
              </Box>
            )}

            {/* Errors log */}
            {result.errors && result.errors.length > 0 && (
              <Box>
                <Typography variant="caption" sx={{ color: 'error.main', fontWeight: 700, display: 'block', mb: 0.5 }}>
                  Errors ({result.errors.length}):
                </Typography>
                <Box sx={{ 
                  maxHeight: 100, 
                  overflowY: 'auto', 
                  p: 1, 
                  borderRadius: 2, 
                  background: 'rgba(239, 68, 68, 0.03)', 
                  border: '1px solid rgba(239, 68, 68, 0.1)' 
                }}>
                  {result.errors.map((e: string, idx: number) => (
                    <Typography key={idx} variant="caption" sx={{ display: 'block', color: 'error.light', mb: 0.4, fontSize: '0.72rem' }}>
                      • {e}
                    </Typography>
                  ))}
                </Box>
              </Box>
            )}
          </Paper>
        )}
      </CardContent>
    </Card>
  );
};

export const SeparationUpload: React.FC = () => {
  return (
    <Box className="fade-in-section" sx={{ pb: 6 }}>
      <Box sx={{ mb: 4, textAlign: 'center' }}>
        <Typography variant="h5" sx={{ fontWeight: 800, mb: 1 }}>
          Separation Records Ingestion
        </Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary', maxWidth: 600, mx: 'auto' }}>
          Upload separation workbooks to sync trainee Dates of Leaving (DOL) and update statuses.
          Master Separation automatically imports every valid separation sheet found in the workbook.
          Individual uploads are provided for future standalone scheme files.
        </Typography>
      </Box>

      <Grid container spacing={3} sx={{ maxWidth: 1200, mx: 'auto' }}>
        {/* Recommended Master Separation Upload Card */}
        <Grid size={{ xs: 12 }}>
          <UploadCard
            title="Master Separation (Recommended)"
            recommended={true}
            templatePath="/templates/Separation_Template.xlsx"
            description="Download the master template containing sample separation sheets for NAPS, BTECH, and MTECH."
            tooltipText="Using the master template ensures all sheets are classified and ingested automatically."
            uploadUrl="/api/uploads/separation"
            uploadMode="MASTER"
            color="secondary"
            noteText="Upload workbook containing all separation sheets. Automatically process every valid Separation sheet for NAPS, B.TECH, M.TECH, and future schemes."
          />
        </Grid>

        {/* Separation note */}
        <Grid size={{ xs: 12 }}>
          <Divider sx={{ my: 2, borderColor: 'rgba(255, 255, 255, 0.05)' }}>
            <Typography variant="caption" sx={{ color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
              Individual Scheme Uploads
            </Typography>
          </Divider>
        </Grid>

        {/* NAPS Separation Upload Card */}
        <Grid size={{ xs: 12, md: 4 }}>
          <UploadCard
            title="NAPS Separation"
            templatePath="/templates/Separation_Template.xlsx"
            description="Download the template and upload separation records belonging exclusively to NAPS scheme."
            tooltipText="Ensure the sheet contains Trainee ID or Ticket Number and Separation Date matching NAPS."
            uploadUrl="/api/uploads/separation"
            uploadMode="NAPS"
            color="secondary"
            noteText="Ingest separations exclusively for the National Apprenticeship Promotion Scheme (NAPS)."
          />
        </Grid>

        {/* B.TECH Separation Upload Card */}
        <Grid size={{ xs: 12, md: 4 }}>
          <UploadCard
            title="B.TECH Separation"
            templatePath="/templates/Separation_Template.xlsx"
            description="Download the template and upload separation records belonging exclusively to B.TECH scheme."
            tooltipText="Ensure the sheet contains Trainee ID or Ticket Number and Separation Date matching BTECH."
            uploadUrl="/api/uploads/separation"
            uploadMode="BTECH"
            color="secondary"
            noteText="Ingest separations exclusively for the B.TECH Trainee Program."
          />
        </Grid>

        {/* M.TECH Separation Upload Card */}
        <Grid size={{ xs: 12, md: 4 }}>
          <UploadCard
            title="M.TECH Separation"
            templatePath="/templates/Separation_Template.xlsx"
            description="Download the template and upload separation records belonging exclusively to M.TECH scheme."
            tooltipText="Ensure the sheet contains Trainee ID or Ticket Number and Separation Date matching MTECH."
            uploadUrl="/api/uploads/separation"
            uploadMode="MTECH"
            color="secondary"
            noteText="Ingest separations exclusively for the M.TECH Trainee Program."
          />
        </Grid>
      </Grid>
    </Box>
  );
};
