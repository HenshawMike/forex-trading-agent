// src/components/Dashboard.tsx
import React from 'react';
import { Container, Grid, Paper, Typography, Box } from '@mui/material';
// Import the new component
import PendingTradesView from './PendingTradesView';
// Assuming your existing CSS or styling solution
// import './Dashboard.css'; // If you have specific dashboard styles, ensure it doesn't clash with MUI

const Dashboard: React.FC = () => {
  // Placeholder data for other dashboard elements - can be expanded later
  const accountSummary = {
    balance: '$10,250.75',
    equity: '$10,150.20',
    openPl: '-$100.55',
    marginUsage: '5%',
  };

  // const marketOverview = { // This was in the prompt but not used, can be added later
  //   eurUsd: '1.0855 (▲ 0.05%)',
  //   usdJpy: '149.20 (▼ 0.10%)',
  //   gold: '$2030.50 (▲ 0.25%)',
  // };

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" gutterBottom component="div" sx={{ mb: 3 }}>
        Trading Dashboard
      </Typography>

      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2, display: 'flex', flexDirection: 'column', height: 140, justifyContent: 'center' }}>
            <Typography component="h2" variant="subtitle1" color="text.secondary" gutterBottom>Balance</Typography>
            <Typography component="p" variant="h5">{accountSummary.balance}</Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2, display: 'flex', flexDirection: 'column', height: 140, justifyContent: 'center' }}>
            <Typography component="h2" variant="subtitle1" color="text.secondary" gutterBottom>Equity</Typography>
            <Typography component="p" variant="h5">{accountSummary.equity}</Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2, display: 'flex', flexDirection: 'column', height: 140, justifyContent: 'center' }}>
            <Typography component="h2" variant="subtitle1" color="text.secondary" gutterBottom>Open P/L</Typography>
            <Typography component="p" variant="h5" sx={{ color: accountSummary.openPl.startsWith('-') ? 'error.main' : 'success.main' }}>
              {accountSummary.openPl}
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2, display: 'flex', flexDirection: 'column', height: 140, justifyContent: 'center' }}>
            <Typography component="h2" variant="subtitle1" color="text.secondary" gutterBottom>Margin Usage</Typography>
            <Typography component="p" variant="h5">{accountSummary.marginUsage}</Typography>
          </Paper>
        </Grid>
      </Grid>

      {/* Integrate the PendingTradesView component */}
      <Grid container spacing={3}>
        <Grid item xs={12}>
          {/* PendingTradesView will manage its own Paper/styling internally based on its current implementation */}
          <PendingTradesView />
        </Grid>

        {/* Future sections for charts, agent status, etc. can be added here */}
        {/*
        <Grid item xs={12} md={8} lg={9}>
          <Paper sx={{ p: 2, display: 'flex', flexDirection: 'column', height: 240 }}>
             <Typography variant="h6">Market Chart</Typography>
             Chart Component Placeholder
          </Paper>
        </Grid>
        <Grid item xs={12} md={4} lg={3}>
          <Paper sx={{ p: 2, display: 'flex', flexDirection: 'column', height: 240 }}>
             <Typography variant="h6">Agent Status</Typography>
             Agent Status Placeholder
          </Paper>
        </Grid>
        */}
      </Grid>

      <Box sx={{ pt: 4, mt: 2 }}> {/* Added mt: 2 for spacing from content above */}
        <Typography variant="body2" color="text.secondary" align="center">
          TradingAgents - Forex Dashboard
        </Typography>
      </Box>
    </Container>
  );
};

export default Dashboard;
