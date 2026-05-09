import React from 'react';
import {
  AbsoluteFill,
  OffthreadVideo,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
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
    [0, 8, durationInFrames - 15, durationInFrames - 5],
    [0, 1, 1, 0],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
  );

  const brandOpacity = interpolate(frame, [0, 10], [0, 0.8], {
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill style={{ backgroundColor: '#000' }}>
      <OffthreadVideo
        src={staticFile(src)}
        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
      />

      {/* Top gradient for hook text readability */}
      <AbsoluteFill
        style={{
          background: 'linear-gradient(to bottom, rgba(0,0,0,0.75) 0%, transparent 40%)',
        }}
      />

      {/* Hook text — top left */}
      <AbsoluteFill
        style={{
          opacity: hookOpacity,
          justifyContent: 'flex-start',
          alignItems: 'flex-start',
          padding: '36px 32px',
        }}
      >
        <div
          style={{
            color: '#FFFFFF',
            fontFamily: 'sans-serif',
            fontWeight: 900,
            fontSize: 38,
            lineHeight: 1.15,
            maxWidth: '88%',
            textShadow: '2px 3px 10px rgba(0,0,0,0.95)',
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
          padding: '20px 28px',
        }}
      >
        <div
          style={{
            color: '#00D4AA',
            fontFamily: 'sans-serif',
            fontWeight: 700,
            fontSize: 17,
            letterSpacing: '1.5px',
            textShadow: '1px 1px 6px rgba(0,0,0,0.9)',
          }}
        >
          VICIPEPTIDES.COM
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
