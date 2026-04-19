import { useIsFetching } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';

/**
 * Global top progress bar — appears on any React Query fetch or navigation.
 * Animates 0→70% quickly, crawls to 85%, snaps to 100% + fades out.
 */
export default function TopProgressBar() {
  const isFetching = useIsFetching();
  const location = useLocation();
  const [progress, setProgress] = useState(0);
  const [visible, setVisible] = useState(false);
  const timerRef = useRef(null);

  const startProgress = () => {
    setVisible(true);
    setProgress(0);
    let p = 0;
    timerRef.current = setInterval(() => {
      p += p < 70 ? 15 : p < 85 ? 1 : 0.3;
      setProgress(Math.min(p, 85));
    }, 100);
  };

  const completeProgress = () => {
    clearInterval(timerRef.current);
    setProgress(100);
    setTimeout(() => setVisible(false), 400);
    setTimeout(() => setProgress(0), 500);
  };

  useEffect(() => {
    if (isFetching > 0) {
      startProgress();
    } else {
      completeProgress();
    }
    return () => clearInterval(timerRef.current);
  }, [isFetching]);

  // Also trigger on route change
  useEffect(() => {
    startProgress();
    const t = setTimeout(completeProgress, 300);
    return () => { clearTimeout(t); clearInterval(timerRef.current); };
  }, [location.pathname]);

  if (!visible && progress === 0) return null;

  return (
    <div className="fixed top-0 left-0 right-0 z-[999] h-[3px] bg-transparent pointer-events-none">
      <div
        className="h-full transition-all ease-out"
        style={{
          width: `${progress}%`,
          backgroundColor: '#3B6D11',
          transitionDuration: progress === 100 ? '200ms' : '400ms',
          opacity: visible ? 1 : 0,
          transition: `width ${progress === 100 ? '200ms' : '400ms'} ease-out, opacity 300ms ease`,
        }}
      />
    </div>
  );
}
