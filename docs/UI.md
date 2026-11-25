# Arr Studio UI Design

## Design Tokens

- **Primary color**: #1a1a1a (dark background)
- **Secondary color**: #4285f4 (Google Blue)
- **Text**: #ffffff (white text)
- **Muted text**: #999999 (gray text)
- **Accent**: #4caf50 (green)
- **Warning**: #ff9800 (amber)
- **Error**: #f44336 (red)
- **Background**: #1a1a1a (dark gray)
- **Border**: #333333 (dark gray)
- **Surface**: #212121 (dark gray)
- **Spacing**: 8px base

## Components

### Topbar
- Logo mark (left)
- "Arr Studio" title (center)
- Live indicator (right)
- Search input (right)
- Refresh button (right)

### Sidebar
- Tabs: Recent, Downloads, Activity
- Filters: All, Sonarr, Radarr
- Content area: poster grid, detail drawer

### Poster Grid
- Auto-fill minmax(160px, 1fr)
- Gap: 18px
- Skeleton loading state
- Error state with retry

### Queue Rows
- Poster thumbnail (left), title and phase badge (right)
- Phase badge: download (muted), waiting for import (warning), importing
  (primary), import blocked / failed (error), imported (accent)
- Progress bar, footer with size left, speed, ETA
- Summary chips above the rows when items wait for or block import
- Error note on blocked or failed rows when the server reports one

### Detail Drawer
- Close button (top-right)
- Metadata: title, subtitle, year, quality
- Image: poster or fanart
- Tags: series info

## Visual Style

- Dark theme with blurred background
- Gradient overlay on hero section
- Paper-like card design
- Smooth animations
