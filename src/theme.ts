import { createTheme } from '@mui/material/styles';

export const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#263238', // Dark Slate Grey - leaning towards black
      contrastText: '#ffffff',
    },
    secondary: {
      main: '#d32f2f', // Red - for accents, actions
      contrastText: '#ffffff',
    },
    background: {
      default: '#1a1a1a', // Very dark grey, almost black
      paper: '#2c2c2c',   // Slightly lighter for paper elements, cards
    },
    text: {
      primary: '#f5f5f5',    // Off-white for primary text
      secondary: '#bdbdbd', // Light grey for secondary text
    },
    error: {
      main: '#f44336',     // Standard red for errors
    },
    success: {
      main: '#66bb6a',     // Green for success
    },
    info: {
      main: '#29b6f6',      // Light blue for info (an "other colour")
    },
    warning: {
      main: '#ffa726',     // Orange for warning
    },
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
    h4: {
      color: '#f5f5f5', // Ensure headings are visible
    },
    h5: {
      color: '#f5f5f5',
    },
    h6: {
      color: '#e0e0e0',
    },
    // Adjust other typography elements if needed
  },
  components: {
     MuiAppBar: {
         styleOverrides: {
             root: {
                 backgroundColor: '#263238', // primary.main
             }
         }
     },
     MuiButton: {
         styleOverrides: {
             containedSecondary: { // Ensure secondary buttons (red) have good contrast
                 color: '#ffffff',
             }
         }
     }
  }
});
