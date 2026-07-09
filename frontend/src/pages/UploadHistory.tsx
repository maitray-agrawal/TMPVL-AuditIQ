import React, { useState, useEffect } from 'react';
import { 
  Box, 
  Typography, 
  Card, 
  Table, 
  TableBody, 
  TableCell, 
  TableContainer, 
  TableHead, 
  TableRow, 
  Paper, 
  Chip, 
  IconButton, 
  Collapse, 
  TextField, 
  MenuItem, 
  Grid, 
  Button, 
  CircularProgress,
  Pagination
} from '@mui/material';
import { 
  ChevronDown, 
  ChevronUp, 
  Search, 
  AlertTriangle, 
  CheckCircle2, 
  XCircle, 
  RefreshCw, 
  FileSpreadsheet
} from 'lucide-react';
import api from '../api';

interface UploadRecord {
  upload_id: string;
  file_name: string;
  file_hash: string;
  file_size: number;
  upload_type: string;
  uploaded_by: string;
  upload_time: string;
  processing_time: number;
  status: string;
  is_duplicate: boolean;
  workbook_version?: string;
  parser_version?: string;
  application_version?: string;
  sheet_count: number;
  visible_sheet_count: number;
  hidden_sheet_count: number;
  rows_processed: number;
  rows_inserted: number;
  rows_updated: number;
  rows_no_change: number;
  rows_skipped: number;
  rows_failed: number;
  rows_rehired: number;
  rows_inactive: number;
  employee_sheets: string[];
  separation_sheets: string[];
  invoice_sheets: string[];
  remarks?: string;
}

const Row = ({ row }: { row: UploadRecord }) => {
  const [open, setOpen] = useState(false);

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getStatusChip = (status: string) => {
    switch (status) {
      case 'SUCCESS':
        return <Chip size="small" icon={<CheckCircle2 size={14} color="#10b981" />} label="Success" sx={{ bgcolor: 'rgba(16, 185, 129, 0.1)', color: '#10b981', fontWeight: 600 }} />;
      case 'PARTIAL':
        return <Chip size="small" icon={<AlertTriangle size={14} color="#f59e0b" />} label="Partial" sx={{ bgcolor: 'rgba(245, 158, 11, 0.1)', color: '#f59e0b', fontWeight: 600 }} />;
      default:
        return <Chip size="small" icon={<XCircle size={14} color="#ef4444" />} label="Failed" sx={{ bgcolor: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', fontWeight: 600 }} />;
    }
  };

  const getTypeChip = (type: string) => {
    let color = '#a855f7';
    let label = type;
    if (type === 'FULL_SYNC') { color = '#3b82f6'; label = 'Full Sync'; }
    else if (type === 'INCREMENTAL') { color = '#10b981'; label = 'Incremental'; }
    else if (type === 'SEPARATION') { color = '#ec4899'; label = 'Separation'; }
    else if (type === 'INVOICE') { color = '#f59e0b'; label = 'Invoice'; }
    else if (type === 'MIXED') { color = '#6366f1'; label = 'Mixed'; }

    return <Chip size="small" label={label} sx={{ bgcolor: `${color}20`, color: color, borderColor: color, borderWidth: 1, borderStyle: 'solid', fontWeight: 600 }} />;
  };

  const handleDownloadErrors = () => {
    api.get('/reports/validation-errors', { responseType: 'blob' })
      .then((response) => {
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `validation_errors_${row.file_name.split('.')[0]}.xlsx`);
        document.body.appendChild(link);
        link.click();
        link.remove();
      })
      .catch((err) => {
        alert('Failed to download validation error report: ' + err.message);
      });
  };

  return (
    <>
      <TableRow sx={{ '& > *': { borderBottom: 'unset' } }}>
        <TableCell>
          <IconButton size="small" onClick={() => setOpen(!open)} sx={{ color: 'text.secondary' }}>
            {open ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
          </IconButton>
        </TableCell>
        <TableCell sx={{ fontWeight: 600, color: '#fff' }}>{row.file_name}</TableCell>
        <TableCell>{getTypeChip(row.upload_type)}</TableCell>
        <TableCell>{getStatusChip(row.status)}</TableCell>
        <TableCell>
          {row.is_duplicate ? (
            <Chip size="small" icon={<AlertTriangle size={14} color="#f59e0b" />} label="Duplicate" sx={{ bgcolor: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b', fontWeight: 600 }} />
          ) : (
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>New</Typography>
          )}
        </TableCell>
        <TableCell sx={{ color: 'text.secondary' }}>{row.uploaded_by}</TableCell>
        <TableCell sx={{ color: 'text.secondary' }}>{row.upload_time}</TableCell>
      </TableRow>
      <TableRow>
        <TableCell style={{ paddingBottom: 0, paddingTop: 0 }} colSpan={7}>
          <Collapse in={open} timeout="auto" unmountOnExit>
            <Box sx={{ margin: 2, p: 2, borderRadius: 2, bgcolor: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)' }}>
              <Typography variant="subtitle2" gutterBottom component="div" sx={{ color: '#fff', fontWeight: 700, mb: 2 }}>
                Upload Detailed Metadata
              </Typography>
              <Grid container spacing={3}>
                <Grid size={{ xs: 12, md: 6 }}>
                  <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
                    <strong style={{ color: '#fff' }}>File SHA-256 Hash: </strong> {row.file_hash}
                  </Typography>
                  <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
                    <strong style={{ color: '#fff' }}>File Size: </strong> {formatBytes(row.file_size)}
                  </Typography>
                  <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
                    <strong style={{ color: '#fff' }}>Processing Time: </strong> {row.processing_time.toFixed(2)} seconds
                  </Typography>
                  <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
                    <strong style={{ color: '#fff' }}>Workbook Version: </strong> {row.workbook_version || 'N/A'} (Parser: v{row.parser_version || '2.0.0'})
                  </Typography>
                  {row.remarks && (
                    <Box sx={{ mt: 1.5, p: 1, borderRadius: 1, bgcolor: 'rgba(245, 158, 11, 0.05)', border: '1px solid rgba(245, 158, 11, 0.15)', display: 'flex', gap: 1, alignItems: 'center' }}>
                      <AlertTriangle size={16} color="#f59e0b" style={{ flexShrink: 0 }} />
                      <Typography variant="caption" sx={{ color: '#f59e0b', fontWeight: 500 }}>
                        {row.remarks}
                      </Typography>
                    </Box>
                  )}
                </Grid>
                
                <Grid size={{ xs: 12, md: 6 }}>
                  <Typography variant="body2" sx={{ color: '#fff', fontWeight: 600, mb: 1 }}>Row Ingestion Stats:</Typography>
                  <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1.5, mb: 2 }}>
                    <Box sx={{ p: 1, bgcolor: 'rgba(255,255,255,0.01)', borderRadius: 1, textAlign: 'center' }}>
                      <Typography variant="caption" sx={{ color: 'text.secondary' }}>Processed</Typography>
                      <Typography variant="body1" sx={{ fontWeight: 700, color: '#fff' }}>{row.rows_processed}</Typography>
                    </Box>
                    <Box sx={{ p: 1, bgcolor: 'rgba(16,185,129,0.05)', borderRadius: 1, textAlign: 'center' }}>
                      <Typography variant="caption" sx={{ color: '#10b981' }}>Inserted</Typography>
                      <Typography variant="body1" sx={{ fontWeight: 700, color: '#10b981' }}>{row.rows_inserted}</Typography>
                    </Box>
                    <Box sx={{ p: 1, bgcolor: 'rgba(59,130,246,0.05)', borderRadius: 1, textAlign: 'center' }}>
                      <Typography variant="caption" sx={{ color: '#3b82f6' }}>Updated</Typography>
                      <Typography variant="body1" sx={{ fontWeight: 700, color: '#3b82f6' }}>{row.rows_updated}</Typography>
                    </Box>
                    <Box sx={{ p: 1, bgcolor: 'rgba(99,102,241,0.05)', borderRadius: 1, textAlign: 'center' }}>
                      <Typography variant="caption" sx={{ color: '#6366f1' }}>Rehired</Typography>
                      <Typography variant="body1" sx={{ fontWeight: 700, color: '#6366f1' }}>{row.rows_rehired}</Typography>
                    </Box>
                    <Box sx={{ p: 1, bgcolor: 'rgba(236,72,153,0.05)', borderRadius: 1, textAlign: 'center' }}>
                      <Typography variant="caption" sx={{ color: '#ec4899' }}>Deactivated</Typography>
                      <Typography variant="body1" sx={{ fontWeight: 700, color: '#ec4899' }}>{row.rows_inactive}</Typography>
                    </Box>
                    <Box sx={{ p: 1, bgcolor: 'rgba(239,68,68,0.05)', borderRadius: 1, textAlign: 'center' }}>
                      <Typography variant="caption" sx={{ color: '#ef4444' }}>Failed</Typography>
                      <Typography variant="body1" sx={{ fontWeight: 700, color: '#ef4444' }}>{row.rows_failed}</Typography>
                    </Box>
                  </Box>

                  {row.rows_failed > 0 && (
                    <Button
                      variant="outlined"
                      color="error"
                      size="small"
                      startIcon={<FileSpreadsheet size={16} />}
                      onClick={handleDownloadErrors}
                      sx={{ textTransform: 'none', fontWeight: 600 }}
                    >
                      Download Row Validation Error Report
                    </Button>
                  )}
                </Grid>
              </Grid>
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>
    </>
  );
};

export const UploadHistory: React.FC = () => {
  const [records, setRecords] = useState<UploadRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploadType, setUploadType] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [page, setPage] = useState<number>(1);
  const [total, setTotal] = useState<number>(0);
  const limit = 10;

  const fetchHistory = () => {
    setLoading(true);
    const offset = (page - 1) * limit;
    api.get('/uploads/history', {
      params: {
        upload_type: uploadType || undefined,
        query: searchQuery || undefined,
        limit,
        offset
      }
    })
    .then((resp) => {
      setRecords(resp.data.uploads);
      setTotal(resp.data.total);
      setLoading(false);
    })
    .catch((err) => {
      console.error(err);
      setLoading(false);
    });
  };

  useEffect(() => {
    fetchHistory();
  }, [page, uploadType]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchHistory();
  };

  return (
    <Box sx={{ color: '#fff' }}>
      {/* Title */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 800, background: 'linear-gradient(135deg, #fff 0%, #a5f3fc 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            Upload History
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5 }}>
            Audit trail of SAP employee files and monthly vendor invoices ingested.
          </Typography>
        </Box>
        <Button 
          variant="contained" 
          startIcon={<RefreshCw size={16} />}
          onClick={fetchHistory}
          sx={{
            background: 'linear-gradient(135deg, #6366f1 0%, #06b6d4 100%)',
            boxShadow: '0 4px 12px rgba(6, 182, 212, 0.25)',
            textTransform: 'none',
            fontWeight: 600
          }}
        >
          Refresh Logs
        </Button>
      </Box>

      {/* Filters Card */}
      <Card sx={{ p: 2, mb: 3, bgcolor: 'rgba(30, 41, 59, 0.5)', border: '1px solid rgba(255,255,255,0.06)', backdropFilter: 'blur(16px)' }}>
        <form onSubmit={handleSearch}>
          <Grid container spacing={2} sx={{ alignItems: 'center' }}>
            <Grid size={{ xs: 12, md: 5 }}>
              <TextField
                fullWidth
                size="small"
                variant="outlined"
                placeholder="Search file name, operator, or remarks..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                slotProps={{
                  input: {
                    startAdornment: <Box sx={{ mr: 1, color: 'text.secondary', display: 'flex' }}><Search size={18} /></Box>
                  }
                }}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              <TextField
                fullWidth
                select
                size="small"
                label="File/Upload Type"
                value={uploadType}
                onChange={(e) => { setUploadType(e.target.value); setPage(1); }}
              >
                <MenuItem value="">All Ingestion Types</MenuItem>
                <MenuItem value="FULL_SYNC">Full sync (Employee Master)</MenuItem>
                <MenuItem value="INCREMENTAL">Incremental (Employee Master)</MenuItem>
                <MenuItem value="SEPARATION">Separations</MenuItem>
                <MenuItem value="INVOICE">Invoices</MenuItem>
                <MenuItem value="MIXED">Mixed (Master + Separation)</MenuItem>
              </TextField>
            </Grid>
            <Grid size={{ xs: 12, md: 3 }}>
              <Button 
                fullWidth 
                type="submit" 
                variant="contained" 
                sx={{ bgcolor: '#6366f1', '&:hover': { bgcolor: '#4f46e5' }, textTransform: 'none', fontWeight: 600, height: 40 }}
              >
                Search Ingestion Trail
              </Button>
            </Grid>
          </Grid>
        </form>
      </Card>

      {/* Table Container */}
      <TableContainer component={Paper} sx={{ bgcolor: 'rgba(30, 41, 59, 0.4)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 2 }}>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 8 }}>
            <CircularProgress size={40} sx={{ color: '#06b6d4' }} />
          </Box>
        ) : records.length === 0 ? (
          <Box sx={{ p: 8, textAlign: 'center' }}>
            <AlertTriangle size={36} color="#f59e0b" style={{ margin: '0 auto 12px auto' }} />
            <Typography variant="body1" sx={{ color: '#fff', fontWeight: 600 }}>No Upload Records Found</Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5 }}>Try broadening your search criteria or uploading a new file.</Typography>
          </Box>
        ) : (
          <>
            <Table aria-label="upload history table">
              <TableHead sx={{ bgcolor: 'rgba(15, 23, 42, 0.3)' }}>
                <TableRow>
                  <TableCell width="60" />
                  <TableCell sx={{ color: '#fff', fontWeight: 700 }}>File Name</TableCell>
                  <TableCell sx={{ color: '#fff', fontWeight: 700 }}>Sync Type</TableCell>
                  <TableCell sx={{ color: '#fff', fontWeight: 700 }}>Status</TableCell>
                  <TableCell sx={{ color: '#fff', fontWeight: 700 }}>Duplicate Check</TableCell>
                  <TableCell sx={{ color: '#fff', fontWeight: 700 }}>Uploaded By</TableCell>
                  <TableCell sx={{ color: '#fff', fontWeight: 700 }}>Date Ingested</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {records.map((row) => (
                  <Row key={row.upload_id} row={row} />
                ))}
              </TableBody>
            </Table>
            {/* Pagination */}
            {total > limit && (
              <Box sx={{ display: 'flex', justifyContent: 'center', p: 3, borderTop: '1px solid rgba(255, 255, 255, 0.06)' }}>
                <Pagination 
                  count={Math.ceil(total / limit)} 
                  page={page} 
                  onChange={(_, value) => setPage(value)} 
                  color="primary"
                  sx={{
                    '& .MuiPaginationItem-root': { color: 'rgba(255,255,255,0.7)' },
                    '& .Mui-selected': { bgcolor: '#6366f1', color: '#fff' }
                  }}
                />
              </Box>
            )}
          </>
        )}
      </TableContainer>
    </Box>
  );
};
