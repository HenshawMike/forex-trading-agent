import React from 'react';
import { Box, Slider, Typography, Button } from '@mui/material';

function ResearchDepth({ data, onUpdate, onNext, onBack }) {
  const handleDepthChange = (_, value) => {
    onUpdate({ ...data, researchDepth: value });
  };

  return (
    <Box sx={{ mt: 2 }}>
      <Typography gutterBottom>Research Depth Level</Typography>
      <Slider
        value={data.researchDepth}
        onChange={handleDepthChange}
        step={1}
        marks
        min={1}
        max={5}
        valueLabelDisplay="auto"
      />
      <Box sx={{ mt: 3, display: 'flex', gap: 2 }}>
        <Button onClick={onBack}>Back</Button>
        <Button variant="contained" onClick={onNext}>
          Start Analysis
        </Button>
      </Box>
    </Box>
  );
}

export default ResearchDepth;
