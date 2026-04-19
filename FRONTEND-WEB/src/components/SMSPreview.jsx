import { useState } from 'react';
import PropTypes from 'prop-types';
import { MessageSquare, X, Send, CheckCircle } from 'lucide-react';

const MAX_SMS = 160;
const WARN_THRESHOLD = 140;

/**
 * 160-char SMS preview component with live character counter and confirm modal.
 */
export default function SMSPreview({ message: initialMessage, farmName, onConfirm, onClose }) {
  const [message, setMessage] = useState(initialMessage || '');
  const [sent, setSent] = useState(false);
  const charCount = message.length;
  const isOverWarning = charCount > WARN_THRESHOLD;
  const isOverLimit = charCount > MAX_SMS;

  const handleSend = async () => {
    if (isOverLimit) return;
    await onConfirm?.(message);
    setSent(true);
    setTimeout(() => {
      setSent(false);
      onClose?.();
    }, 1500);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50 px-4">
      <div className="bg-white rounded-2xl w-full max-w-md shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-neutral-100">
          <div className="flex items-center gap-2">
            <MessageSquare size={18} className="text-teal-400" />
            <h2 className="text-sm font-semibold text-neutral-800">SMS Preview</h2>
          </div>
          <button onClick={onClose} className="text-neutral-400 hover:text-neutral-600" aria-label="Close modal" id="sms-modal-close">
            <X size={18} />
          </button>
        </div>

        {/* Farm label */}
        <div className="px-5 py-3 bg-neutral-50 border-b border-neutral-100">
          <p className="text-xs text-neutral-500">
            Sending to: <strong className="text-neutral-700">{farmName || 'All Farms'}</strong>
          </p>
        </div>

        {/* Message editor */}
        <div className="px-5 py-4">
          <label className="text-xs font-medium text-neutral-500 uppercase tracking-wider block mb-2">
            Message
          </label>
          <div className="relative">
            <div className="bg-neutral-50 rounded-xl border border-neutral-200 p-3 font-mono text-xs leading-relaxed text-neutral-800 min-h-[80px] whitespace-pre-wrap">
              {message || <span className="text-neutral-300">No message entered…</span>}
            </div>
          </div>
          {/* Editable textarea */}
          <textarea
            id="sms-message-input"
            className="input mt-3 font-mono text-xs resize-none h-20"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            maxLength={MAX_SMS}
            placeholder="Edit SMS message…"
          />
          {/* Character counter */}
          <div className="flex items-center justify-between mt-1.5">
            <p className="text-xs text-neutral-400">
              {charCount < WARN_THRESHOLD ? 'Messages over 160 chars are split.' : ''}
            </p>
            <p
              className={`text-xs font-semibold tabular-nums ${
                isOverLimit
                  ? 'text-danger-600'
                  : isOverWarning
                  ? 'text-amber-500'
                  : 'text-neutral-400'
              }`}
            >
              {charCount} / {MAX_SMS}
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="px-5 py-4 border-t border-neutral-100 flex gap-3 justify-end">
          <button onClick={onClose} className="btn-secondary" id="sms-cancel-btn">
            Cancel
          </button>
          <button
            onClick={handleSend}
            disabled={isOverLimit || sent}
            id="sms-confirm-btn"
            className={`flex items-center gap-2 btn-teal ${isOverLimit || sent ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {sent ? (
              <>
                <CheckCircle size={14} />
                Sent!
              </>
            ) : (
              <>
                <Send size={14} />
                Confirm & Send
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

SMSPreview.propTypes = {
  message: PropTypes.string,
  farmName: PropTypes.string,
  onConfirm: PropTypes.func,
  onClose: PropTypes.func.isRequired,
};
