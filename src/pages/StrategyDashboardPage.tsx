// src/pages/StrategyDashboardPage.tsx
import React, { useState, useEffect, useCallback } from 'react';
import { Button, List, ListItem, ListItemText, Paper, Typography, IconButton, Container, Box, CircularProgress, Alert } from '@mui/material';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';

interface StrategySummary {
  strategy_id: string;
  name: string;
  author?: string;
  updated_at?: string;
}

const StrategyDashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [strategies, setStrategies] = useState<StrategySummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStrategies = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/strategies');
      if (!response.ok) {
        throw new Error(`Failed to fetch strategies: ${response.status}`);
      }
      const data: StrategySummary[] = await response.json();
      setStrategies(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStrategies();
  }, [fetchStrategies]);

  const handleDelete = async (strategyId: string) => {
    if (window.confirm('Are you sure you want to delete this strategy?')) {
      try {
        const response = await fetch(`/api/strategies/${strategyId}`, { method: 'DELETE' });
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || `Failed to delete strategy: ${response.status}`);
        }
        // Refresh strategies list
        fetchStrategies();
      } catch (err: any) {
        setError(`Delete error: ${err.message}`);
      }
    }
  };

  if (loading) {
    return <Container sx={{display: 'flex', justifyContent: 'center', mt: 5}}><CircularProgress /></Container>;
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Paper elevation={3} sx={{ p: { xs: 2, md: 3 } }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" component="h1">
            Strategies Dashboard
          </Typography>
          <Button variant="contained" color="secondary" component={RouterLink} to="/strategies/new">
            Create New Strategy
          </Button>
        </Box>

        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        {strategies.length === 0 && !loading && (
          <Alert severity="info">No strategies found. Get started by creating one!</Alert>
        )}

        {strategies.length > 0 && (
          <List>
            {strategies.map((strategy) => (
              <ListItem
                key={strategy.strategy_id}
                divider
                secondaryAction={
                  <>
                    <IconButton edge="end" aria-label="edit" component={RouterLink} to={`/strategies/edit/${strategy.strategy_id}`}>
                      <EditIcon />
                    </IconButton>
                    <IconButton edge="end" aria-label="delete" onClick={() => handleDelete(strategy.strategy_id)} sx={{ ml: 1 }}>
                      <DeleteIcon />
                    </IconButton>
                  </>
                }
              >
                <ListItemText
                  primary={strategy.name}
                  secondary={`Author: ${strategy.author || 'N/A'} - Last Updated: ${strategy.updated_at ? new Date(strategy.updated_at).toLocaleDateString() : 'N/A'}`}
                />
              </ListItem>
            ))}
          </List>
        )}
      </Paper>
    </Container>
  );
};

export default StrategyDashboardPage;
