import React, { useEffect, useState } from 'react';
import { io } from 'socket.io-client';
import {
    Box,
    Typography,
    List,
    ListItem,
    // ListItemText, // Not explicitly used in the final detailed layout
    Button,
    Paper,
    CircularProgress,
    Alert,
    Grid,
    Chip
} from '@mui/material';

interface TradeRiskAssessment {
    risk_score?: number;
    assessment_summary?: string;
    proceed_with_trade?: boolean;
    recommended_modifications?: {
        sl?: number;
        tp?: number;
        size_factor?: number;
    };
}

interface TradeProposal {
    trade_id: string;
    pair: string;
    side: 'buy' | 'sell';
    type: 'market' | 'limit' | 'stop';
    entry_price?: number | null;
    sl: number;
    tp: number;
    calculated_position_size: number;
    meta_rationale?: string;
    sub_agent_confidence?: number;
    risk_assessment?: TradeRiskAssessment;
    status: string;
}

const PendingTradesView: React.FC = () => {
    const [pendingTrades, setPendingTrades] = useState<TradeProposal[]>([]);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    // Function to re-fetch trades or update UI after action
    const fetchPendingTrades = async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await fetch('http://127.0.0.1:5000/api/pending_trades');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data: TradeProposal[] = await response.json();
            // The /api/pending_trades endpoint in api_server.py was updated to only return 'pending_approval'
            setPendingTrades(data);
        } catch (e: any) {
            console.error("Failed to fetch pending trades:", e);
            setError(`Failed to fetch pending trades: ${e.message}. Ensure the mock API server is running on http://127.0.0.1:5000.`);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchPendingTrades(); // Initial fetch
    }, []);

    useEffect(() => {
        const socket = io('http://127.0.0.1:5000');

        socket.on('connect', () => {
            console.log('Connected to WebSocket server');
        });

        socket.on('new_trade_proposal', (proposal: TradeProposal) => {
            console.log('Received new trade proposal via WebSocket:', proposal);
            setPendingTrades(prevTrades => {
                // Avoid duplicates and update existing if necessary
                const existingTradeIndex = prevTrades.findIndex(t => t.trade_id === proposal.trade_id);
                if (existingTradeIndex !== -1) {
                    // Update existing trade if details can change, for now, let's assume new means new
                    // or replace if status changes and it becomes pending again (less likely for this event)
                    // For simplicity, if ID matches, could replace or ignore.
                    // Let's add if not present, or replace if present to get latest state.
                    const updatedTrades = [...prevTrades];
                    updatedTrades[existingTradeIndex] = proposal;
                    return updatedTrades;
                } else {
                    // Add as new if it's genuinely new and status is pending_approval
                    if (proposal.status === 'pending_approval') {
                       return [proposal, ...prevTrades]; // Add to the top
                    }
                    return prevTrades;
                }
            });
        });

        socket.on('disconnect', () => {
            console.log('Disconnected from WebSocket server');
        });

        return () => {
            console.log('Disconnecting WebSocket');
            socket.disconnect();
        };
    }, []); // Empty dependency array means this effect runs once on mount and cleans up on unmount


    const handleApprove = async (tradeId: string) => {
        console.log(`Attempting to approve Trade ${tradeId}...`);
        // Optimistically update UI or show loading state for this specific trade
        // For now, just log and re-fetch the whole list for simplicity
        try {
            const response = await fetch(`http://127.0.0.1:5000/api/trades/${tradeId}/approve`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
            });
            if (!response.ok) {
                let errorMsg = `HTTP error! status: ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorMsg = errorData.message || errorData.error || errorMsg;
                } catch (jsonError) {
                    // Ignore if response is not JSON
                }
                throw new Error(errorMsg);
            }
            const result = await response.json();
            console.log(`Trade ${tradeId} approval API response:`, result.message);
            fetchPendingTrades(); // Re-fetch to get updated list
        } catch (e: any) {
            console.error(`Failed to approve trade ${tradeId}:`, e);
            setError(`Failed to approve trade ${tradeId}: ${e.message}`);
            // Optionally, re-fetch even on error to ensure UI consistency if server state did change partially
            // fetchPendingTrades();
        }
    };

    const handleReject = async (tradeId: string) => {
        console.log(`Attempting to reject Trade ${tradeId}...`);
        try {
            const response = await fetch(`http://127.0.0.1:5000/api/trades/${tradeId}/reject`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
            });
            if (!response.ok) {
                let errorMsg = `HTTP error! status: ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorMsg = errorData.message || errorData.error || errorMsg;
                } catch (jsonError) {
                     // Ignore if response is not JSON
                }
                throw new Error(errorMsg);
            }
            const result = await response.json();
            console.log(`Trade ${tradeId} rejection API response:`, result.message);
            fetchPendingTrades(); // Re-fetch to get updated list
        } catch (e: any) {
            console.error(`Failed to reject trade ${tradeId}:`, e);
            setError(`Failed to reject trade ${tradeId}: ${e.message}`);
        }
    };

    if (loading && pendingTrades.length === 0) { // Show initial loading only if no trades are yet visible
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', p: 3 }}>
                <CircularProgress />
                <Typography sx={{ ml: 2 }}>Loading pending trades...</Typography>
            </Box>
        );
    }

    if (pendingTrades.length === 0 && !error && !loading) {
        return <Alert severity="info" sx={{ m: 2 }}>No trades currently pending approval.</Alert>;
    }

    return (
        <Box>
            {error && <Alert severity="error" sx={{ mt: 2, mb: 2 }}>{error}</Alert>}
            <Paper elevation={3} sx={{ p: 2, mt: 2 }}>
                <Typography variant="h5" gutterBottom component="div">
                    Trades Pending Approval
                </Typography>
                {/* Redundant check if already handled above, but safe */}
                {pendingTrades.length === 0 && !loading && !error && (
                     <Alert severity="info" sx={{ m: 2 }}>No trades currently pending approval.</Alert>
                )}
                <List>
                    {pendingTrades.map((trade) => (
                        <ListItem
                            key={trade.trade_id}
                            divider
                            sx={(theme) => ({ // Added theme access here
                                mb: 2,
                                p: 2,
                                border: `1px solid ${theme.palette.divider}`, // Use theme divider
                                borderRadius: '8px',
                                // boxShadow: '0 2px 4px rgba(0,0,0,0.1)', // Keep or remove based on dark theme preference
                                // Use more visible background based on theme and side
                                backgroundColor: trade.side === 'buy' ? 'rgba(102, 187, 106, 0.15)' : 'rgba(244, 67, 54, 0.15)',
                                '&:hover': { // Optional: Add hover effect
                                    borderColor: theme.palette.primary.light,
                                }
                            })}
                        >
                            <Grid container spacing={2} alignItems="flex-start">
                                <Grid item xs={12} md={8}>
                                    <Typography variant="h6" component="div" sx={{ display: 'flex', alignItems: 'center', gap: 1}}>
                                        {trade.pair}
                                        <Chip
                                            label={trade.side.toUpperCase()}
                                            color={trade.side === 'buy' ? 'success' : 'error'}
                                            size="small"
                                            sx={{ fontWeight: 'bold' }}
                                        />
                                         <Chip
                                            label={trade.type.toUpperCase()}
                                            variant="outlined"
                                            size="small"
                                            // sx={{ borderColor: theme.palette.text.secondary, color: theme.palette.text.secondary }} // Ensure visibility for outlined chip
                                        />
                                    </Typography>
                                    <Typography variant="caption" color="text.secondary" display="block">ID: {trade.trade_id}</Typography>

                                    <Typography variant="body2" sx={{mt: 1}}>
                                        {trade.type !== 'market' && trade.entry_price ? `Entry: ${trade.entry_price} | ` : 'Entry: Market | '}
                                        SL: {trade.sl} | TP: {trade.tp}
                                    </Typography>
                                    <Typography variant="body2">Size: {trade.calculated_position_size} lots</Typography>
                                    {trade.sub_agent_confidence !== undefined && (
                                        <Typography variant="body2">Agent Confidence: {(trade.sub_agent_confidence * 100).toFixed(0)}%</Typography>
                                    )}
                                    {trade.risk_assessment && (
                                        <Box sx={(theme) => ({ // Added theme access here
                                            mt: 1.5,
                                            p:1.5,
                                            border: `1px dashed ${theme.palette.divider}`, // Use theme divider
                                            borderRadius: '4px',
                                            backgroundColor: alpha(theme.palette.background.default, 0.5) // Slightly different background
                                        })}>
                                            <Typography variant="overline" display="block" sx={{fontWeight: 'bold', lineHeight: 1.2, mb: 0.5}}>Risk Assessment:</Typography>
                                            <Typography variant="caption" display="block">Summary: {trade.risk_assessment.assessment_summary}</Typography>
                                            <Typography variant="caption" display="block">Score: {trade.risk_assessment.risk_score?.toFixed(2)} (Proceed: {trade.risk_assessment.proceed_with_trade ? 'Yes' : 'No'})</Typography>
                                            {trade.risk_assessment.recommended_modifications?.size_factor !== 1.0 && trade.risk_assessment.recommended_modifications?.size_factor !== undefined && (
                                                <Typography variant="caption" display="block" sx={{color: 'warning.main'}}>Recommended Size Factor: {trade.risk_assessment.recommended_modifications.size_factor}</Typography>
                                            )}
                                        </Box>
                                    )}
                                    {trade.meta_rationale && <Typography variant="body2" sx={{mt:1, fontStyle: 'italic', color: 'text.secondary'}}>Rationale: {trade.meta_rationale}</Typography>}
                                </Grid>
                                <Grid item xs={12} md={4} sx={{ display: 'flex', flexDirection: { xs: 'row', md: 'column'}, gap: 1, justifyContent: 'flex-start', alignItems: 'stretch' }}>
                                    <Button
                                        variant="contained"
                                        color="success"
                                        onClick={() => handleApprove(trade.trade_id)}
                                        fullWidth
                                        sx={{mb: {xs: 0, md: 1}}}
                                    >
                                        Approve
                                    </Button>
                                    <Button
                                        variant="outlined"
                                        color="error"
                                        onClick={() => handleReject(trade.trade_id)}
                                        fullWidth
                                    >
                                        Reject
                                    </Button>
                                </Grid>
                            </Grid>
                        </ListItem>
                    ))}
                </List>
            </Paper>
        </Box>
    );
};

export default PendingTradesView;
