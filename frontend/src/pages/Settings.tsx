import React, { useEffect, useState } from 'react';
import { 
  Box, 
  Card, 
  CardContent, 
  Typography, 
  Button, 
  TextField, 
  Grid, 
  CircularProgress,
  Alert,
  Divider
} from '@mui/material';
import { Save, ShieldCheck } from 'lucide-react';
import api from '../api';

export const Settings: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Settings fields
  const [joiningMax, setJoiningMax] = useState<number>(1200);
  const [days180Max, setDays180Max] = useState<number>(600);
  const [totalMax, setTotalMax] = useState<number>(1800);
  const [minDays, setMinDays] = useState<number>(30);

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        setLoading(true);
        const res = await api.get('/settings');
        setJoiningMax(res.data.joining_payment_max);
        setDays180Max(res.data.days180_payment_max);
        setTotalMax(res.data.max_payable_per_trainee);
        setMinDays(res.data.min_days_reimbursement);
      } catch (err) {
        console.error("Failed to load settings", err);
      } finally {
        setLoading(false);
      }
    };
    fetchSettings();
  }, []);

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);
      setSuccess(false);

      const payload = {
        joining_payment_max: Number(joiningMax),
        days180_payment_max: Number(days180Max),
        max_payable_per_trainee: Number(totalMax),
        min_days_reimbursement: Number(minDays),
      };

      await api.post('/settings', payload);
      setSuccess(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save settings.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '40vh' }}>
        <CircularProgress color="secondary" />
      </Box>
    );
  }

  return (
    <Box className="fade-in-section" sx={{ maxWidth: 600, mx: 'auto', mt: 3 }}>
      <Card>
        <CardContent sx={{ p: 4 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3 }}>
            <Box sx={{ p: 1, borderRadius: 2, background: 'rgba(99,102,241,0.1)', color: 'primary.main' }}>
              <ShieldCheck size={24} />
            </Box>
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 700 }}>Validation Rules Thresholds</Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>Configure financial and compliance parameters of the audit engine</Typography>
            </Box>
          </Box>

          {success && (
            <Alert severity="success" sx={{ mb: 3, borderRadius: 2 }}>
              Settings saved and updated successfully.
            </Alert>
          )}

          {error && (
            <Alert severity="error" sx={{ mb: 3, borderRadius: 2 }}>
              {error}
            </Alert>
          )}

          <Grid container spacing={3}>
            {/* Limit 1: Joining Payout */}
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                fullWidth
                label="Maximum Joining Reimbursement (₹)"
                type="number"
                value={joiningMax}
                onChange={(e) => setJoiningMax(Number(e.target.value))}
                disabled={saving}
              />
            </Grid>

            {/* Limit 2: 180 Days Payout */}
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                fullWidth
                label="Maximum 180-Days Payout (₹)"
                type="number"
                value={days180Max}
                onChange={(e) => setDays180Max(Number(e.target.value))}
                disabled={saving}
              />
            </Grid>

            {/* Limit 3: Total Cap */}
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                fullWidth
                label="Total Cap Per Trainee (₹)"
                type="number"
                value={totalMax}
                onChange={(e) => setTotalMax(Number(e.target.value))}
                disabled={saving}
              />
            </Grid>

            {/* Limit 4: Min days for DOJ */}
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                fullWidth
                label="Min Days Tenure for Joining Reimbursement"
                type="number"
                value={minDays}
                onChange={(e) => setMinDays(Number(e.target.value))}
                disabled={saving}
              />
            </Grid>
          </Grid>

          <Divider sx={{ my: 4, borderColor: 'rgba(255,255,255,0.08)' }} />

          <Button
            fullWidth
            variant="contained"
            color="primary"
            startIcon={<Save size={18} />}
            onClick={handleSave}
            disabled={saving}
            sx={{ py: 1.2 }}
          >
            {saving ? <CircularProgress size={20} /> : 'Save System Parameters'}
          </Button>
        </CardContent>
      </Card>
    </Box>
  );
};
