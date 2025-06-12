// src/components/StrategyEditor.tsx
import React, { useState, useEffect } from 'react';
import { TextField, Button, Select, MenuItem, FormControl, InputLabel, Box, Paper, Typography, Grid } from '@mui/material';
import { useNavigate } from 'react-router-dom';

interface StrategyData {
  strategy_id?: string;
  name: string;
  author: string;
  description: string;
  content_type: 'plaintext' | 'markdown';
  content: string;
  target_instrument?: string;
  target_timeframe?: string;
  // created_at and updated_at are handled by backend
}

interface StrategyEditorProps {
  initialData?: StrategyData;
  strategyId?: string; // If present, we are in edit mode
  onSaveSuccess?: () => void; // Callback for successful save
}

const StrategyEditor: React.FC<StrategyEditorProps> = ({ initialData, strategyId, onSaveSuccess }) => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<Omit<StrategyData, 'strategy_id'>>({
    name: '',
    author: '',
    description: '',
    content_type: 'markdown',
    content: '',
    target_instrument: '',
    target_timeframe: '',
    ...initialData,
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialData) {
      // Ensure all fields from initialData are spread, even if not in the default Omit<> type.
      // This is okay because initialData is StrategyData which can have strategy_id.
      // The state itself (formData) is correctly typed as Omit<StrategyData, 'strategy_id'>
      // because we don't edit the ID directly in the form.
      setFormData(prev => ({ ...prev, ...initialData }));
    }
  }, [initialData]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | { name?: string; value: unknown }>) => {
    const target = e.target as HTMLInputElement; // Type assertion

    // Handle MUI Select specifically as its event structure is different for `onChange`
    // It provides an event object where target might not be what we expect for name/value directly.
    // Instead, the event's second argument or a different structure might be used,
    // or the event.target might have name and value on a nested field.
    // For MUI Select, the `name` is on `e.target.name` and `value` is on `e.target.value`.
    // The `as any` for Select's onChange in the JSX is a common workaround for these typing complexities.
    setFormData({
      ...formData,
      [target.name!]: target.value,
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    const url = strategyId ? `/api/strategies/${strategyId}` : '/api/strategies';
    const method = strategyId ? 'PUT' : 'POST';

    try {
      const response = await fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `Failed to save strategy. Status: ${response.status}`);
      }

      // const savedStrategy = await response.json(); // Contains the full strategy with ID, timestamps
      if (onSaveSuccess) {
        onSaveSuccess();
      } else {
        navigate('/strategies'); // Default navigation if no callback
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Paper elevation={3} sx={{ p: { xs: 2, md: 4 }, mt: 2 }}>
      <Typography variant="h5" gutterBottom component="div" sx={{ mb: 3 }}>
        {strategyId ? 'Edit Strategy' : 'Create New Strategy'}
      </Typography>
      <form onSubmit={handleSubmit}>
        <Grid container spacing={3}>
          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Strategy Name"
              name="name"
              value={formData.name}
              onChange={handleChange}
              required
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Author"
              name="author"
              value={formData.author}
              onChange={handleChange}
              required
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Description"
              name="description"
              value={formData.description}
              onChange={handleChange}
              multiline
              rows={3}
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <FormControl fullWidth>
              <InputLabel id="content-type-label">Content Type</InputLabel>
              <Select
                labelId="content-type-label"
                label="Content Type"
                name="content_type"
                value={formData.content_type}
                onChange={handleChange as any} // MUI Select onChange type can be tricky
              >
                <MenuItem value="plaintext">Plain Text</MenuItem>
                <MenuItem value="markdown">Markdown</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Strategy Content / Rules"
              name="content"
              value={formData.content}
              onChange={handleChange}
              multiline
              rows={10}
              required
              placeholder="Document your strategy rules, entry/exit conditions, risk management, etc."
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Target Instrument (e.g., EUR/USD)"
              name="target_instrument"
              value={formData.target_instrument}
              onChange={handleChange}
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Target Timeframe (e.g., H1, D1)"
              name="target_timeframe"
              value={formData.target_timeframe}
              onChange={handleChange}
            />
          </Grid>
          {error && (
            <Grid item xs={12}>
              <Typography color="error" sx={{ mt: 2 }}>{error}</Typography>
            </Grid>
          )}
          <Grid item xs={12} sx={{ mt: 2, display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
             <Button type="button" variant="outlined" onClick={() => navigate(-1)} disabled={isSubmitting}>
                 Cancel
             </Button>
             <Button type="submit" variant="contained" color="secondary" disabled={isSubmitting}>
              {isSubmitting ? 'Saving...' : (strategyId ? 'Save Changes' : 'Create Strategy')}
            </Button>
          </Grid>
        </Grid>
      </form>
    </Paper>
  );
};

export default StrategyEditor;
