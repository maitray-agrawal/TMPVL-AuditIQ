import React, { useState, useEffect } from 'react';
import { AppBar, Toolbar, Typography, Box, Chip } from '@mui/material';
import { CloudOff, Clock } from 'lucide-react';

interface HeaderProps {
  currentPage: string;
}

export const Header: React.FC<HeaderProps> = ({ currentPage }) => {
  const [time, setTime] = useState<string>('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTime(now.toLocaleString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
        second: '2-digit',
        hour12: true,
        weekday: 'short',
        month: 'short',
        day: 'numeric'
      }));
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const getPageTitle = () => {
    switch (currentPage) {
      case 'dashboard':
        return 'System Overview & Metrics';
      case 'employees':
        return 'Trainee Database (Employee Master)';
      case 'upload_bdc':
        return 'BDC Master Workbook Import';
      case 'upload_separation':
        return 'Separation Workbook Import';
      case 'upload_invoice':
        return 'Quess Monthly Invoice Import';
      case 'validation':
        return 'Billing Validation & Fraud Engine';
      case 'reconciliation':
        return 'Invoice Reconciliation Engine';
      case 'ledger':
        return 'Trainee Payment Ledger';
      case 'reports':
        return 'Reconciliation Report Exports';
      case 'logs':
        return 'System Audit Logs';
      case 'settings':
        return 'Policy Configurations & Caps';
      default:
        return 'TMPVL Billing Audit';
    }
  };

  return (
    <AppBar
      position="fixed"
      sx={{
        width: 'calc(100% - 260px)',
        ml: '260px',
        background: 'rgba(7, 10, 19, 0.75)',
        backdropFilter: 'blur(12px)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
        boxShadow: 'none',
        zIndex: 1100,
      }}
    >
      <Toolbar sx={{ justifyContent: 'space-between', px: 3, py: 1.5 }}>
        {/* Title */}
        <Typography 
          variant="h5" 
          sx={{ 
            fontWeight: 700, 
            fontSize: '1.25rem',
            background: 'linear-gradient(90deg, #fff 0%, rgba(255,255,255,0.7) 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}
        >
          {getPageTitle()}
        </Typography>

        {/* Info Right */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2.5 }}>
          {/* Clock */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'text.secondary' }}>
            <Clock size={16} />
            <Typography variant="body2" sx={{ fontSize: '0.85rem', fontWeight: 500 }}>
              {time}
            </Typography>
          </Box>

          {/* Connection Status */}
          <Chip
            icon={<CloudOff size={14} color="#06b6d4" />}
            label="OFFLINE SECURITY MODE"
            size="small"
            sx={{
              background: 'rgba(6, 182, 212, 0.1)',
              border: '1px solid rgba(6, 182, 212, 0.2)',
              color: '#06b6d4',
              fontWeight: 700,
              fontSize: '0.7rem',
              letterSpacing: '0.05em',
              '& .MuiChip-icon': {
                color: '#06b6d4 !important',
              }
            }}
          />
        </Box>
      </Toolbar>
    </AppBar>
  );
};
