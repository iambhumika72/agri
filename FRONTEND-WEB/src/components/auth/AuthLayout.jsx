import PropTypes from 'prop-types';

export default function AuthLayout({ children }) {
  return (
    <div className="min-h-screen flex">
      <div
        className="hidden md:flex flex-col justify-center w-[40%] flex-shrink-0 relative overflow-hidden"
        style={{ background: '#0f1f0f' }}
      >
        {/* SVG Illustration */}
        <div className="absolute inset-0 w-full h-full">
          <svg viewBox="0 0 400 500" className="w-full h-full object-cover preserveAspectRatio='xMidYMax slice'">
            {/* Sky */}
            <rect width="400" height="200" fill="#0f1f0f" />
            <circle cx="340" cy="60" r="30" fill="#EF9F27" />
            <rect x="50" y="80" width="60" height="20" rx="10" fill="#ffffff" opacity="0.8" />
            <rect x="250" y="120" width="80" height="25" rx="12.5" fill="#ffffff" opacity="0.8" />
            
            {/* Ground */}
            <rect y="200" width="400" height="300" fill="#2d4a1e" />
            <line x1="0" y1="240" x2="400" y2="240" stroke="#3B6D11" strokeWidth="2" />
            <line x1="0" y1="280" x2="400" y2="280" stroke="#3B6D11" strokeWidth="2" />
            <line x1="0" y1="320" x2="400" y2="320" stroke="#3B6D11" strokeWidth="2" />
            <line x1="0" y1="360" x2="400" y2="360" stroke="#3B6D11" strokeWidth="2" />
            <line x1="0" y1="400" x2="400" y2="400" stroke="#3B6D11" strokeWidth="2" />
            
            {/* Farmer */}
            <rect x="80" y="240" width="30" height="60" fill="#8B5E3C" rx="5" />
            <circle cx="95" cy="220" r="15" fill="#C68642" />
            <path d="M75 215 L115 215 L95 190 Z" fill="#EF9F27" />
            <line x1="70" y1="250" x2="110" y2="280" stroke="#8B5E3C" strokeWidth="6" strokeLinecap="round" />
            <line x1="110" y1="280" x2="110" y2="320" stroke="#C68642" strokeWidth="4" />
            <line x1="100" y1="320" x2="130" y2="320" stroke="#C68642" strokeWidth="4" />
            
            {/* Wheat/Crops */}
            <line x1="280" y1="320" x2="280" y2="220" stroke="#97C459" strokeWidth="3" />
            <ellipse cx="280" cy="210" rx="6" ry="12" fill="#97C459" />
            
            <line x1="310" y1="340" x2="310" y2="250" stroke="#97C459" strokeWidth="3" />
            <ellipse cx="310" cy="240" rx="6" ry="12" fill="#97C459" />
            
            <line x1="340" y1="310" x2="340" y2="210" stroke="#97C459" strokeWidth="3" />
            <ellipse cx="340" cy="200" rx="6" ry="12" fill="#97C459" />
          </svg>
        </div>

        <div className="absolute bottom-16 left-0 w-full text-center px-6">
          <p className="text-white font-medium text-[28px] tracking-wide mb-1">KrishiAI</p>
          <p className="text-white text-[14px]">किसानों के लिए स्मार्ट खेती</p>
          <p className="text-[#9FE1CB] text-[13px] mt-1">Smart farming for every farmer</p>
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center p-6 bg-white overflow-y-auto">
        <div className="w-full max-w-[420px]">
          {children}
        </div>
      </div>
    </div>
  );
}

AuthLayout.propTypes = {
  children: PropTypes.node.isRequired,
};
