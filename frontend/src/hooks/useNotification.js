import { useState, useCallback, useRef } from 'react';

const useNotification = () => {
  const [permission, setPermission] = useState(() => {
    if (typeof Notification !== 'undefined') {
      return Notification.permission;
    }
    return 'default';
  });
  const audioContextRef = useRef(null);

  const requestPermission = useCallback(async () => {
    if (typeof Notification === 'undefined') {
      console.log('This browser does not support desktop notification');
      return;
    }

    try {
      const result = await Notification.requestPermission();
      setPermission(result);
      // Initialize AudioContext on user interaction
      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
      }
    } catch (error) {
      console.error('Failed to request notification permission:', error);
    }
  }, []);

  const playSound = useCallback(() => {
    try {
      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
      }

      const ctx = audioContextRef.current;
      const oscillator = ctx.createOscillator();
      const gainNode = ctx.createGain();

      oscillator.connect(gainNode);
      gainNode.connect(ctx.destination);

      oscillator.type = 'sine';
      oscillator.frequency.setValueAtTime(880, ctx.currentTime); // A5
      oscillator.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.1); // Drop to A4

      gainNode.gain.setValueAtTime(0.1, ctx.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);

      oscillator.start();
      oscillator.stop(ctx.currentTime + 0.5);
    } catch (error) {
      console.error('Failed to play sound:', error);
    }
  }, []);

  const sendNotification = useCallback((title, options = {}) => {
    if (permission === 'granted') {
      try {
        // SW経由での通知（モバイルで信頼性が高い）を試みる
        if ('serviceWorker' in navigator && navigator.serviceWorker.ready) {
          navigator.serviceWorker.ready.then(registration => {
            registration.showNotification(title, {
              icon: '/pwa-192x192.png', // PWAアイコンがあれば
              vibrate: [200, 100, 200],
              ...options
            });
          });
        } else if (typeof Notification !== 'undefined') {
          // 通常のNotification API
          new Notification(title, {
            icon: '/pwa-192x192.png',
            vibrate: [200, 100, 200],
            ...options
          });
        }
        playSound();
      } catch (error) {
        console.error('Failed to send notification:', error);
      }
    }
  }, [permission, playSound]);

  return {
    permission,
    requestPermission,
    sendNotification
  };
};

export default useNotification;
