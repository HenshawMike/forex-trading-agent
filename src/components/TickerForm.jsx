import React from 'react';
import { Box, TextField, Button } from '@mui/material';

function TickerForm({ data, onUpdate, onNext }) {
  const handleSubmit = (e) => {
    e.preventDefault();
    onNext();
  };

  return (
    <Box component="form" onSubmit={handleSubmit} sx={{ mt: 2 }}>
      <TextField
        fullWidth
        label="Ticker Symbol"
        value={data.ticker}
        onChange={(e) => onUpdate({ ...data, ticker: e.target.value.toUpperCase() })}
        margin="normal"
        required
      />
      <TextField
        fullWidth
        type="date"
        label="Analysis Date"
        value={data.date}
        onChange={(e) => onUpdate({ ...data, date: e.target.value })}
        margin="normal"
        required
        InputLabelProps={{ shrink: true }}
      />
      <Button
        type="submit"
        variant="contained"
        sx={{ mt: 3 }}
        disabled={!data.ticker}
      >
        Next
      </Button>
    </Box>
  );
}

export default TickerForm;
