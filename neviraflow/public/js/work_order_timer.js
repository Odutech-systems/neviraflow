(() => {
    frappe.ui.form.on('Work Order', {
        refresh(frm) {
            // Build floating timer container once
            ensureTimerUI();
            
            // Render immediately based on current doc state
            renderTimer(frm);
            
            // Poll every second to keep time fresh while "In Progress"
            startTicker(frm);
            
            // Bind workflow Action buttons (Start, Pause, Resume, Finish, Cancelled)
            bindWorkflowButtons(frm);
        }
    });

    let tickInterval = null;

    function ensureTimerUI() {
        if (document.getElementById('wo-floating-timer')) return;
        
        const wrap = document.createElement('div');
        wrap.style.pointerEvents = 'auto';
        wrap.id = 'wo-floating-timer';
        wrap.style.position = 'absolute';
        wrap.style.left = '50%';
        wrap.style.top = '40px';
        wrap.style.transform = 'translateX(-50%)';
        wrap.style.zIndex = 100;
        wrap.style.color = '#0e0d0dff';
        wrap.style.padding = '12px 16px';
        wrap.style.borderRadius = '12px';
        wrap.style.boxShadow = '0 6px 20px rgba(0,0,0,0.25)';
        wrap.style.fontFamily = 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace';
        wrap.style.display = 'inline-flex';
        wrap.style.alignItems = 'baseline';
        wrap.style.gap = '8px';
        wrap.style.whiteSpace = 'nowrap';
        
        wrap.innerHTML = `
            <span style="font-size:12px;opacity:.8;margin-bottom:4px;">Work Order Progress</span>
            <span id="wo-timer-display" style="font-size:28px;font-weight:700;letter-spacing:1px;">00:00:00</span>
            <span id="wo-timer-status" style="font-size:11px;opacity:.75;margin-top:4px;">—</span>
        `;
        
        document.body.appendChild(wrap);
    }

    function bindWorkflowButtons(frm) {
        // Rebind each refresh (delegate at document level)
        $(document).off('click.wo-timer');
        
        const map = {
            'Start': 'Start',
            'Pause': 'Pause',
            'Resume': 'Resume',
            'Finish': 'Finish',
            'Completed': 'Finish', // some setups name the action differently
            'Cancelled': 'Cancelled'
        };
        
        $(document).on('click.wo-timer', 'button, a.dropdown-item, .menu-btn', function() {
            const label = ($(this).text() || '').trim();
            const match = Object.keys(map).find(k => label === k);
            if (!match) return;
            
            // Hint server which action we clicked, so it can be read in before_save
            frm.doc._workflow_clicked_action = map[match];
            
            // Immediately reflect on UI (optimistic), actual source of truth is server on save/refresh.
            // We don't change doc fields here; just update the timer display state optimistically.
            tickOnce(frm, /*optimisticAction=*/map[match]);
            
            // Let Frappe continue default click behavior...
            setTimeout(() => {
                // Clear the hint after save to avoid stale values
                if (frm && frm.doc) delete frm.doc._workflow_clicked_action;
            }, 6000);
        });
    }

    function startTicker(frm) {
        stopTicker();
        tickInterval = setInterval(() => tickOnce(frm), 1000);
    }

    function stopTicker() {
        if (tickInterval) {
            clearInterval(tickInterval);
            tickInterval = null;
        }
    }

    function tickOnce(frm, optimisticAction=null) {
        const displayEl = document.getElementById('wo-timer-display');
        const statusEl = document.getElementById('wo-timer-status');
        if (!displayEl || !statusEl || !frm || !frm.doc) return;
        
        const total = parseInt(frm.doc.custom_timer_total_seconds || 0, 10);
        const lastResumeMs = frm.doc.custom_timer_last_resume_at ? toMs(frm.doc.custom_timer_last_resume_at) : null;
        const state = (frm.doc.workflow_state || frm.doc.status || '').trim();
        
        let effectiveState = state;
        if (optimisticAction === 'Start' || optimisticAction === 'Resume') effectiveState = 'In Progress';
        if (optimisticAction === 'Pause') effectiveState = 'Paused';
        if (optimisticAction === 'Finish' || optimisticAction === 'Cancelled') effectiveState = 'Completed';
        
        let runningSeconds = total;
        if (effectiveState === 'In Progress' && lastResumeMs) {
            const deltaSec = Math.max(0, Math.floor((Date.now() - lastResumeMs) / 1000));
            runningSeconds += deltaSec;
        }
        
        displayEl.textContent = formatHMS(runningSeconds);
        statusEl.textContent = effectiveState ? `Status: ${effectiveState}` : '—';
    }

    // Parse ERP/Frappe datetime strings to a millisecond epoch using only built-ins
    function toMs(ts) {
        if (!ts) return null;
        const s = String(ts).trim();
        // Safari doesn't parse "YYYY-MM-DD HH:mm:ss" well—normalize to ISO.
        // If it already has 'T' or a timezone, Date.parse will handle it.
        const iso = s.includes('T') ? s : (s.replace(' ', 'T') + 'Z');
        const t = Date.parse(iso);
        return Number.isNaN(t) ? null : t;
    }

    function formatHMS(totalSeconds) {
        const s = Math.max(0, parseInt(totalSeconds || 0, 10));
        const hh = Math.floor(s / 3600);
        const mm = Math.floor((s % 3600) / 60);
        const ss = s % 60;
        return `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`;
    }

    function renderTimer(frm) {
        tickOnce(frm);
    }
})();