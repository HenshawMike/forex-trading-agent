import React from 'react';
import { Box, FormGroup, FormControlLabel, Checkbox, Button } from '@mui/material';

function AnalystSelection({ data, onUpdate, onNext, onBack }) {
  const analysts = [
    { value: 'market', label: 'Market Analyst' },
    { value: 'social', label: 'Social Analyst' },
    { value: 'news', label: 'News Analyst' },
    { value: 'fundamentals', label: 'Fundamentals Analyst' },
  ];

  const handleAnalystChange = (value) => {
    const updated = data.selectedAnalysts.includes(value)
      ? data.selectedAnalysts.filter(a => a !== value)
      : [...data.selectedAnalysts, value];
    onUpdate({ ...data, selectedAnalysts: updated });
  };

  return (
    <Box sx={{ mt: 2 }}>
      <FormGroup>
        {analysts.map((analyst) => (
          <FormControlLabel
            key={analyst.value}
            control={
              <Checkbox
                checked={data.selectedAnalysts.includes(analyst.value)}
                onChange={() => handleAnalystChange(analyst.value)}
              />
            }
            label={analyst.label}
          />
        ))}
      </FormGroup>
      <Box sx={{ mt: 3, display: 'flex', gap: 2 }}>
        <Button onClick={onBack}>Back</Button>
        <Button
          variant="contained"
          onClick={onNext}
          disabled={data.selectedAnalysts.length === 0}
        >
          Next
        </Button>
      </Box>
    </Box>
  );
}

export default AnalystSelection;
