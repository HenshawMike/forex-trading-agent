import React from 'react';
import { Box, Typography, LinearProgress } from '@mui/material';

function AgentProgress({ activeStep }) {
  const agents = {
    0: [],
    1: ['Market Analyst', 'Social Analyst', 'News Analyst', 'Fundamentals Analyst'],
    2: ['Research Team', 'Trading Team'],
    3: ['Risk Management', 'Portfolio Manager'],
  };

  return (
    <Box sx={{ p: 2, bgcolor: 'background.paper', borderRadius: 1 }}>
      <Typography variant="h6" gutterBottom>
        Agent Progress
      </Typography>
      {agents[activeStep].map((agent) => (
        <Box key={agent} sx={{ mt: 2 }}>
          <Typography variant="body2" gutterBottom>
            {agent}
          </Typography>
          <LinearProgress />
        </Box>
      ))}
    </Box>
  );
}

export default AgentProgress;
