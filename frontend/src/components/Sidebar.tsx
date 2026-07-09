import React from 'react';
import { 
  LayoutDashboard, 
  Users, 
  FileUp, 
  UserMinus, 
  Receipt, 
  CheckSquare, 
  BarChart3,
  BookOpen, 
  Download, 
  History, 
  Settings as SettingsIcon,
  ShieldCheck,
  ClipboardList
} from 'lucide-react';
import { 
  Box, 
  List, 
  ListItem, 
  ListItemButton, 
  ListItemIcon, 
  ListItemText, 
  Typography, 
  Divider 
} from '@mui/material';


interface SidebarProps {
  currentPage: string;
  onPageChange: (page: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentPage, onPageChange }) => {
  const menuItems = [
    { id: 'dashboard', label: 'Dashboard', icon: <LayoutDashboard size={20} /> },
    { id: 'employees', label: 'Employee Master', icon: <Users size={20} /> },
    { id: 'upload_bdc', label: 'BDC Upload', icon: <FileUp size={20} /> },
    { id: 'upload_separation', label: 'Separation Upload', icon: <UserMinus size={20} /> },
    { id: 'upload_invoice', label: 'Invoice Upload', icon: <Receipt size={20} /> },
    { id: 'upload_history', label: 'Upload History', icon: <ClipboardList size={20} /> },
    { id: 'validation', label: 'Validation Engine', icon: <CheckSquare size={20} /> },
    { id: 'reconciliation', label: 'Reconciliation', icon: <BarChart3 size={20} /> },
    { id: 'ledger', label: 'Payment Ledger', icon: <BookOpen size={20} /> },
    { id: 'reports', label: 'Reports', icon: <Download size={20} /> },
    { id: 'logs', label: 'Audit Logs', icon: <History size={20} /> },
    { id: 'settings', label: 'Settings', icon: <SettingsIcon size={20} /> },
  ];



  return (
    <Box
      sx={{
        width: 260,
        height: '100vh',
        background: 'rgba(17, 24, 39, 0.7)',
        backdropFilter: 'blur(20px)',
        borderRight: '1px solid rgba(255, 255, 255, 0.08)',
        display: 'flex',
        flexDirection: 'column',
        position: 'fixed',
        top: 0,
        left: 0,
        zIndex: 1200,
      }}
    >
      {/* Brand Header */}
      <Box sx={{ p: 3, display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <Box 
          sx={{ 
            p: 1, 
            borderRadius: 2, 
            background: 'linear-gradient(135deg, #6366f1 0%, #06b6d4 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            boxShadow: '0 4px 12px rgba(99, 102, 241, 0.3)'
          }}
        >
          <ShieldCheck size={24} />
        </Box>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 800, fontSize: '1.05rem', lineHeight: 1.2, letterSpacing: '0.05em', color: '#fff' }}>
            TMPVL AUDIT
          </Typography>
          <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.4)', fontWeight: 600, letterSpacing: '0.1em' }}>
            FRAUD SHIELD
          </Typography>
        </Box>
      </Box>

      <Divider sx={{ borderColor: 'rgba(255, 255, 255, 0.08)' }} />

      {/* Navigation List */}
      <Box sx={{ flexGrow: 1, overflowY: 'auto', py: 2 }}>
        <List sx={{ px: 1.5, gap: 0.5, display: 'flex', flexDirection: 'column' }}>
          {menuItems.map((item) => {
            const isActive = currentPage === item.id;
            return (
              <ListItem key={item.id} disablePadding>
                <ListItemButton
                  onClick={() => onPageChange(item.id)}
                  sx={{
                    borderRadius: 2,
                    py: 1.2,
                    px: 2,
                    background: isActive ? 'linear-gradient(90deg, rgba(99, 102, 241, 0.15) 0%, rgba(6, 182, 212, 0.03) 100%)' : 'transparent',
                    borderLeft: isActive ? '3px solid #6366f1' : '3px solid transparent',
                    color: isActive ? '#fff' : 'text.secondary',
                    transition: 'all 0.2s ease',
                    '&:hover': {
                      background: 'rgba(255, 255, 255, 0.03)',
                      color: '#fff',
                      '& .MuiListItemIcon-root': {
                        color: '#6366f1',
                      }
                    },
                  }}
                >
                  <ListItemIcon
                    sx={{
                      minWidth: 36,
                      color: isActive ? '#6366f1' : 'inherit',
                      transition: 'color 0.2s ease',
                    }}
                  >
                    {item.icon}
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Typography variant="body2" sx={{ fontSize: '0.925rem', fontWeight: isActive ? 600 : 500 }}>
                        {item.label}
                      </Typography>
                    }
                  />
                </ListItemButton>
              </ListItem>
            );
          })}
          

        </List>
      </Box>

      {/* Footer Branding */}
      <Box sx={{ p: 2, borderTop: '1px solid rgba(255, 255, 255, 0.08)', textAlign: 'center' }}>
        <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.75rem' }}>
          v2.0.0 • Offline Production
        </Typography>
      </Box>
    </Box>
  );
};
