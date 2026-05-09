import React from 'react';
import {
  AbsoluteFill,
  OffthreadVideo,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  Easing,
} from 'remotion';

type Props = {
  src: string;
  hookText: string;
};

export const ViciClip: React.FC<Props> = ({ src, hookText }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const hookOpacity = interpolate(
    frame,
    [0, 8, durationInFrames - 12, durationInFrames - 4],
    [0, 1, 1, 0],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
  );

  const brandOpacity = interpolate(frame, [0, 12], [0, 0.9], {
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill style={{ backgroundColor: '#000' }}>
      <OffthreadVideo
        src={staticFile(src)}
        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
      />
      {/* Top gradient */}
      <AbsoluteFill
        style={{
          background: 'linear-gradient(to bottom, rgba(0,0,0,0.7) 0%, transparent 30%)',
        }}
      />
      {/* Hook text — top area, 16:9 layout */}
      <AbsoluteFill
        style={{
          opacity: hookOpacity,
          justifyContent: 'flex-start',
          alignItems: 'flex-start',
          padding: '48px 60px',
        }}
      >
        <div
          style={{
            color: '#FFFFFF',
            fontFamily: 'sans-serif',
            fontWeight: 900,
            fontSize: 52,
            lineHeight: 1.2,
            maxWidth: '75%',
            textShadow: '2px 3px 12px rgba(0,0,0,0.95)',
            letterSpacing: '-0.5px',
          }}
        >
          {hookText}
        </div>
      </AbsoluteFill>
      {/* Brand watermark — bottom right */}
      <AbsoluteFill
        style={{
          opacity: brandOpacity,
          justifyContent: 'flex-end',
          alignItems: 'flex-end',
          padding: '24px 36px',
        }}
      >
        <div
          style={{
            color: '#00D4AA',
            fontFamily: 'sans-serif',
            fontWeight: 700,
            fontSize: 20,
            letterSpacing: '2px',
            textShadow: '1px 1px 8px rgba(0,0,0,0.9)',
          }}
        >
          VICIPEPTIDES.COM
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
