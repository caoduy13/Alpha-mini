import { useEffect, useRef } from 'react';
import type { AppAction } from '../context/AppContext';
import { getStatus } from '../api/endpoints';

export function useRobotStatus(dispatch: React.Dispatch<AppAction>) {
  const dispatchRef = useRef(dispatch);
  dispatchRef.current = dispatch;

  useEffect(() => {
    let alive = true;

    async function tick() {
      try {
        const s = await getStatus();
        if (!alive) {
          return;
        }
        dispatchRef.current({
          type: 'robot/status',
          payload: {
            online: !!s.robot_online,
            ip: String(s.robot_ip ?? ''),
            robotType: String(s.robot_type ?? ''),
          },
        });
      } catch {
        if (!alive) {
          return;
        }
        dispatchRef.current({
          type: 'robot/status',
          payload: { online: false, ip: '', robotType: '' },
        });
      }
    }

    tick();
    const id = setInterval(tick, 5000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);
}
