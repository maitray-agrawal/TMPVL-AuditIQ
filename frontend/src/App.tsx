import React, { useState } from 'react';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { Box } from '@mui/material';

import { theme } from './theme';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';

// Pages
import { Dashboard } from './pages/Dashboard';
import { EmployeeMaster } from './pages/EmployeeMaster';
import { BDCUpload } from './pages/BDCUpload';
import { SeparationUpload } from './pages/SeparationUpload';
import { InvoiceUpload } from './pages/InvoiceUpload';
import { ValidationEngine } from './pages/ValidationEngine';
import { Reconciliation } from './pages/Reconciliation';
import { PaymentLedger } from './pages/PaymentLedger';
import { Reports } from './pages/Reports';
import { AuditLogs } from './pages/AuditLogs';
import { Settings } from './pages/Settings';

const App: React.FC = () => {
  const [currentPage, setCurrentPage] = useState<string>('dashboard');

  const renderPage = () => {
    switch (currentPage) {
      case 'dashboard':
        return <Dashboard onPageChange={setCurrentPage} />;
      case 'employees':
        return <EmployeeMaster />;
      case 'upload_bdc':
        return <BDCUpload />;
      case 'upload_separation':
        return <SeparationUpload />;
      case 'upload_invoice':
        return <InvoiceUpload onPageChange={setCurrentPage} />;
      case 'validation':
        return <ValidationEngine />;
      case 'reconciliation':
        return <Reconciliation />;
      case 'ledger':
        return <PaymentLedger />;
      case 'reports':
        return <Reports />;
      case 'logs':
        return <AuditLogs />;
      case 'settings':
        return <Settings />;
      default:
        return <Dashboard onPageChange={setCurrentPage} />;
    }
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ display: 'flex', minHeight: '100vh' }}>
        {/* Sidebar Left */}
        <Sidebar currentPage={currentPage} onPageChange={setCurrentPage} />

        {/* Layout Right */}
        <Box 
          sx={{ 
            flexGrow: 1, 
            display: 'flex', 
            flexDirection: 'column', 
            width: 'calc(100% - 260px)', 
            ml: '260px',
            minHeight: '100vh' 
          }}
        >
          {/* Header Top */}
          <Header currentPage={currentPage} />

          {/* Main Workspace content */}
          <Box 
            component="main" 
            sx={{ 
              flexGrow: 1, 
              p: 3, 
              pt: '88px', // offset header height
              background: 'transparent',
              overflowY: 'auto'
            }}
          >
            {renderPage()}
          </Box>
        </Box>
      </Box>
    </ThemeProvider>
  );
};

export default App;
