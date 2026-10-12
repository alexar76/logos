/** One quiet, consistent icon family for the analytics workspace. */
export default function Icon({ name, size = 20 }: { name: string; size?: number }) {
  const paths: Record<string, string> = {
    copy: 'M9 9h11v12H9z M15 9V3H4v12h5',
    check: 'm5 12 4 4 10-10',
    close: 'm6 6 12 12 M6 18 18 6',
    chevron: 'm6 9 6 6 6-6',
    right: 'm9 6 6 6-6 6',
    refresh: 'M20 7v5h-5 M4 17v-5h5 M5.5 7a8 8 0 0 1 13-1L20 9 M4 15l1.5 3a8 8 0 0 0 13-1',
    play: 'm8 4 12 8-12 8V4z',
    stop: 'M6 6h12v12H6z',
    download: 'M12 3v12 M7 10l5 5 5-5 M4 16v5h16v-5',
    query: 'M3 12h4l3-8 4 16 3-8h4',
    report: 'M7 3h10v18H7z M10 7h4 M10 11h4 M10 15h4',
    chat: 'M4 4h16v12H9l-5 4V4z M8 8h8 M8 12h5',
    nexus: 'M12 3 3 8l9 5 9-5-9-5z M3 12l9 5 9-5 M3 16l9 5 9-5',
    consumption: 'M4 7h16v14H4z M7 7V3h10v4 M4 12h16 M15 16h2',
    analytics: 'M4 20V10 M10 20V4 M16 20v-7 M22 20H2',
    arrow: 'M5 12h14 M13 6l6 6-6 6',
    sun: 'M12 2v2 M12 20v2 M2 12h2 M20 12h2 M5 5l1.5 1.5 M17.5 17.5l1.5 1.5 M5 19l1.5-1.5 M17.5 6.5l1.5-1.5 M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
    moon: 'M20 15.5A9 9 0 0 1 8.5 4 9 9 0 1 0 20 15.5z',
    globe: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M3 12h18 M12 3c5 5 5 13 0 18-5-5-5-13 0-18',
    mic: 'M9 5a3 3 0 0 1 6 0v6a3 3 0 0 1-6 0V5 M6 10v1a6 6 0 0 0 12 0v-1 M12 17v4 M9 21h6',
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name] || paths.query} /></svg>;
}
