import React from 'react';
import { 
  Box, 
  Button, 
  Typography, 
  Tooltip 
} from '@mui/material';
import { Download } from 'lucide-react';

interface DownloadTemplateButtonProps {
  title: string;
  templatePath: string;
  description: string;
  tooltipText?: string;
}

export const DownloadTemplateButton: React.FC<DownloadTemplateButtonProps> = ({
  title,
  templatePath,
  description,
  tooltipText,
}) => {
  const handleDownload = () => {
    const link = document.createElement('a');
    link.href = templatePath;
    link.download = templatePath.split('/').pop() || 'template.xlsx';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <Box sx={{ mb: 3 }}>
      <Tooltip 
        title={tooltipText || 'Download the template to ensure compatibility'}
        arrow
        placement="top"
      >
        <Button
          variant="outlined"
          color="secondary"
          onClick={handleDownload}
          startIcon={<Download size={18} />}
          sx={{
            py: 1.2,
            px: 2.5,
            borderRadius: 1.5,
            textTransform: 'none',
            fontWeight: 600,
            transition: 'all 0.3s ease-in-out',
            '&:hover': {
              transform: 'translateY(-2px)',
              boxShadow: '0 4px 12px rgba(6, 182, 212, 0.15)',
            },
          }}
        >
          {title}
        </Button>
      </Tooltip>
      <Typography 
        variant="caption" 
        sx={{ 
          display: 'block', 
          mt: 1, 
          color: 'text.secondary',
          fontSize: '0.8rem'
        }}
      >
        {description}
      </Typography>
    </Box>
  );
};
