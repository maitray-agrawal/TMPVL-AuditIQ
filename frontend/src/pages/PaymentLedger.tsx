import React, { useEffect, useState, useRef } from 'react';
import { Box, Card, CardContent, Typography } from '@mui/material';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef } from 'ag-grid-community';
import api from '../api';

interface LedgerRow {
  id: number;
  trainee_id: string;
  trainee_name: string;
  invoice_number: string;
  payment_type: string;
  amount_paid: number;
  payment_date: string;
  extra_data?: {
    invoice_month?: string;
    rejected?: number;
    running_total?: number;
    remaining_balance?: number;
  };
}

const formatCurrency = (value: number | undefined) => {
  if (value === undefined || value === null) return '₹0';
  return `₹${value.toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
};

const getPaymentTypeColor = (type: string) => {
  switch (type) {
    case 'JOINING':
      return '#3b82f6'; // blue
    case '180_DAYS':
      return '#10b981'; // green
    case 'OTHER':
      return '#f59e0b'; // amber
    default:
      return '#6b7280'; // gray
  }
};

export const PaymentLedger: React.FC = () => {
  const [rowData, setRowData] = useState<LedgerRow[]>([]);
  const [loading, setLoading] = useState(false);
  const gridRef = useRef<any>(null);

  const fetchLedger = async () => {
    try {
      setLoading(true);
      const res = await api.get('/ledger');
      setRowData(res.data);
    } catch (err) {
      console.error("Failed to load ledger", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLedger();
  }, []);

  const columnDefs: ColDef[] = [
    { 
      field: 'trainee_id', 
      headerName: 'Trainee ID', 
      sortable: true, 
      filter: true, 
      width: 130,
      pinned: 'left'
    },
    { 
      field: 'trainee_name', 
      headerName: 'Trainee Name', 
      sortable: true, 
      filter: true, 
      width: 200,
      flex: 1
    },
    { 
      field: 'payment_date', 
      headerName: 'Payment Date', 
      sortable: true, 
      filter: true,
      width: 130,
      valueFormatter: params => {
        if (!params.value) return '';
        return new Date(params.value).toLocaleDateString('en-IN');
      }
    },
    { 
      field: 'invoice_number', 
      headerName: 'Invoice Number', 
      sortable: true, 
      filter: true, 
      width: 150
    },
    {
      field: 'extra_data.invoice_month',
      headerName: 'Invoice Month',
      sortable: true,
      filter: true,
      width: 140,
      valueGetter: params => params.data?.extra_data?.invoice_month || '-'
    },
    { 
      field: 'payment_type', 
      headerName: 'Payment Type', 
      sortable: true, 
      filter: true, 
      width: 130,
      cellRenderer: (params: any) => (
        <Box
          sx={{
            backgroundColor: getPaymentTypeColor(params.value),
            color: 'white',
            padding: '4px 8px',
            borderRadius: '4px',
            fontSize: '12px',
            fontWeight: 600,
            textAlign: 'center'
          }}
        >
          {params.value === '180_DAYS' ? '180 Days' : params.value}
        </Box>
      )
    },
    { 
      field: 'amount_paid', 
      headerName: 'Approved Amount (₹)', 
      sortable: true, 
      width: 160,
      valueFormatter: params => formatCurrency(params.value),
      cellStyle: { color: '#10b981', fontWeight: 700, textAlign: 'right' }
    },
    {
      field: 'extra_data.rejected',
      headerName: 'Rejected Amount (₹)',
      sortable: true,
      width: 160,
      valueGetter: params => params.data?.extra_data?.rejected || 0,
      valueFormatter: params => formatCurrency(params.value),
      cellStyle: { color: '#ef4444', fontWeight: 700, textAlign: 'right' }
    },
    {
      field: 'extra_data.running_total',
      headerName: 'Running Total (₹)',
      sortable: true,
      width: 160,
      valueGetter: params => params.data?.extra_data?.running_total || 0,
      valueFormatter: params => formatCurrency(params.value),
      cellStyle: { fontWeight: 600, textAlign: 'right', backgroundColor: 'rgba(59, 130, 246, 0.1)' }
    },
    {
      field: 'extra_data.remaining_balance',
      headerName: 'Remaining Balance (₹)',
      sortable: true,
      width: 160,
      valueGetter: params => params.data?.extra_data?.remaining_balance || 0,
      valueFormatter: params => {
        const val = params.value;
        const formatted = formatCurrency(val);
        return formatted;
      },
      cellStyle: (params: any) => {
        const remaining = params.data?.extra_data?.remaining_balance || 0;
        const color = remaining <= 0 ? '#ef4444' : remaining <= 300 ? '#f59e0b' : '#10b981';
        return { 
          color: color, 
          fontWeight: 600, 
          textAlign: 'right',
          backgroundColor: remaining <= 0 ? 'rgba(239, 68, 68, 0.1)' : 'rgba(16, 185, 129, 0.1)'
        };
      }
    }
  ];

  return (
    <Box className="fade-in-section">
      <Card sx={{ mb: 3 }}>
        <CardContent sx={{ p: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>Payment Ledger & Disbursement History</Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
            Complete ledger of all approved and rejected payments. Tracks running totals and remaining balance against the ₹1800 annual maximum per trainee.
          </Typography>
          <Box sx={{ mt: 2, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <Box>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>Payment Rules:</Typography>
              <Box sx={{ fontSize: '12px', mt: 0.5 }}>
                • Joining Max: ₹1200 | 180 Days Max: ₹600 | Annual Cap: ₹1800
              </Box>
            </Box>
            <Box>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>Kit Limits:</Typography>
              <Box sx={{ fontSize: '12px', mt: 0.5 }}>
                • Max: 3 Shirts, 3 Jeans | If claimed &gt; 5 Shirts, 4 Jeans: Approve only ₹1200
              </Box>
            </Box>
          </Box>
        </CardContent>
      </Card>

      <Box className="ag-theme-quartz ag-theme-quartz-dark" sx={{ height: 'calc(100vh - 300px)', width: '100%' }}>
        <AgGridReact
          ref={gridRef}
          rowData={rowData}
          columnDefs={columnDefs}
          pagination={true}
          paginationPageSize={15}
          animateRows={true}
          loading={loading}
          defaultColDef={{
            resizable: true,
            suppressMovable: false
          }}
        />
      </Box>
    </Box>
  );
};
