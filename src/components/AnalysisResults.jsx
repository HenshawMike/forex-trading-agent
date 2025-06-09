import React from 'react';
import { Box, Typography, Paper, Button } from '@mui/material';

function AnalysisResults({ results, onBack }) {
  if (!results) {
    return <Typography>Loading analysis results...</Typography>;
  }

  return (
    <Box>
      {/* Analyst Team Reports */}
      {results.analyst_reports && (
        <Paper sx={{ p: 2, mb: 2 }}>
          <Typography variant="h6">Analyst Team Reports</Typography>
          {Object.entries(results.analyst_reports).map(([key, report]) => (
            <Box key={key} sx={{ mt: 2 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>
                {key.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')}
              </Typography>
              <Typography variant="body2">{report}</Typography>
            </Box>
          ))}
        </Paper>
      )}

      {/* Final Decision */}
      {results.final_decision && (
        <Paper sx={{ p: 2, mb: 2, bgcolor: 'primary.light' }}>
          <Typography variant="h6" sx={{ color: 'white' }}>
            Final Trading Decision
          </Typography>
          <Typography sx={{ color: 'white' }}>
            {results.final_decision}
          </Typography>
        </Paper>
      )}

      <Button onClick={onBack} sx={{ mt: 2 }}>
        Back to Start
      </Button>
    </Box>
  );
}

export default AnalysisResults;
