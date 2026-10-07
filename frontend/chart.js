/**
 * Buy or Wait? — Personal Liquidity Trajectory Chart
 * High-performance, zero-dependency HTML5 Canvas chart designed with bespoke fintech aesthetics.
 */

class BalanceChart {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!canvasId || !this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.data = null;
        this.currency = 'USD';
        this.hoverIndex = -1;
        this.zoomDays = 90;
        this.isHovering = false;

        this._initEvents();
    }

    _initEvents() {
        if (!this.canvas) return;

        window.addEventListener('resize', () => {
            this.resize();
            this.render();
        });

        this.canvas.addEventListener('mousemove', (e) => {
            if (!this.data || !this.data.timeline || this.data.timeline.length === 0) return;
            const rect = this.canvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            
            const plotArea = this._getPlotArea();
            if (mouseX >= plotArea.x && mouseX <= plotArea.x + plotArea.width) {
                const ratio = (mouseX - plotArea.x) / plotArea.width;
                const timeline = this._getActiveTimeline();
                const idx = Math.min(timeline.length - 1, Math.max(0, Math.round(ratio * (timeline.length - 1))));
                this.hoverIndex = idx;
                this.isHovering = true;
                this.render();
                this._showTooltip(e.clientX, e.clientY, timeline[idx]);
            } else {
                this.isHovering = false;
                this.hoverIndex = -1;
                this.render();
                this._hideTooltip();
            }
        });

        this.canvas.addEventListener('mouseleave', () => {
            this.isHovering = false;
            this.hoverIndex = -1;
            this.render();
            this._hideTooltip();
        });
    }

    setData(data, currency = 'USD') {
        this.data = data;
        this.currency = currency;
        this.hoverIndex = -1;
        this.resize();
        this.render();
    }

    setZoom(days) {
        this.zoomDays = days;
        this.render();
    }

    resize() {
        if (!this.canvas) return;
        const rect = this.canvas.parentElement.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        this.width = rect.width;
        this.height = Math.max(300, rect.height || 300);

        this.canvas.width = this.width * dpr;
        this.canvas.height = this.height * dpr;
        this.canvas.style.width = `${this.width}px`;
        this.canvas.style.height = `${this.height}px`;

        this.ctx.resetTransform();
        this.ctx.scale(dpr, dpr);
    }

    _getActiveTimeline() {
        if (!this.data || !this.data.timeline) return [];
        return this.data.timeline.slice(0, this.zoomDays + 1);
    }

    _getPlotArea() {
        return {
            x: 65,
            y: 20,
            width: this.width - 80,
            height: this.height - 55
        };
    }

    render() {
        if (!this.ctx || !this.canvas) return;
        const ctx = this.ctx;
        ctx.clearRect(0, 0, this.width, this.height);

        const timeline = this._getActiveTimeline();
        if (!timeline || timeline.length === 0) {
            this._renderEmptyState();
            return;
        }

        const plot = this._getPlotArea();

        // Calculate min and max values
        let minVal = Infinity;
        let maxVal = -Infinity;
        const minKeep = (timeline[0] && timeline[0].min_keep !== undefined) ? timeline[0].min_keep : 0;

        timeline.forEach(pt => {
            if (pt.projected_balance < minVal) minVal = pt.projected_balance;
            if (pt.projected_balance > maxVal) maxVal = pt.projected_balance;
            if (pt.baseline_balance !== undefined) {
                if (pt.baseline_balance < minVal) minVal = pt.baseline_balance;
                if (pt.baseline_balance > maxVal) maxVal = pt.baseline_balance;
            }
        });

        if (minKeep < minVal) minVal = minKeep;
        if (minKeep > maxVal) maxVal = minKeep;

        // Add 10% breathing room
        const span = maxVal - minVal || 1000;
        const yMin = Math.floor(minVal - span * 0.10);
        const yMax = Math.ceil(maxVal + span * 0.10);
        const ySpan = yMax - yMin || 1;

        const getY = (val) => plot.y + plot.height - ((val - yMin) / ySpan) * plot.height;
        const getX = (idx) => plot.x + (idx / (timeline.length - 1)) * plot.width;

        // 1. Gridlines and Y-axis labels
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
        ctx.lineWidth = 1;
        ctx.fillStyle = '#64748b';
        ctx.font = '10px "JetBrains Mono", monospace';
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';

        const ySteps = 4;
        for (let i = 0; i <= ySteps; i++) {
            const stepVal = yMin + (i / ySteps) * ySpan;
            const yPos = getY(stepVal);
            ctx.beginPath();
            ctx.moveTo(plot.x, yPos);
            ctx.lineTo(plot.x + plot.width, yPos);
            ctx.stroke();

            ctx.fillText(this._formatCompact(stepVal), plot.x - 8, yPos);
        }

        // 2. Mandatory Reserve Line
        const minKeepY = getY(minKeep);
        if (minKeepY >= plot.y && minKeepY <= plot.y + plot.height) {
            // Reserve shading below threshold
            const dangerGrad = ctx.createLinearGradient(0, minKeepY, 0, plot.y + plot.height);
            dangerGrad.addColorStop(0, 'rgba(244, 63, 94, 0.08)');
            dangerGrad.addColorStop(1, 'rgba(244, 63, 94, 0.01)');
            ctx.fillStyle = dangerGrad;
            ctx.fillRect(plot.x, minKeepY, plot.width, (plot.y + plot.height) - minKeepY);

            // Refined dashed line
            ctx.save();
            ctx.setLineDash([4, 4]);
            ctx.strokeStyle = '#f43f5e';
            ctx.lineWidth = 1.2;
            ctx.beginPath();
            ctx.moveTo(plot.x, minKeepY);
            ctx.lineTo(plot.x + plot.width, minKeepY);
            ctx.stroke();

            ctx.fillStyle = '#f43f5e';
            ctx.font = '600 9.5px "Plus Jakarta Sans", sans-serif';
            ctx.textAlign = 'right';
            ctx.fillText(`RESERVE LIMIT: ${this._formatCompact(minKeep)}`, plot.x + plot.width, minKeepY - 6);
            ctx.restore();
        }

        // 3. Baseline Cashflow (Without purchase)
        if (timeline[0] && timeline[0].baseline_balance !== undefined) {
            ctx.save();
            ctx.setLineDash([3, 3]);
            ctx.strokeStyle = 'rgba(148, 163, 184, 0.35)';
            ctx.lineWidth = 1.2;
            ctx.beginPath();
            for (let i = 0; i < timeline.length; i++) {
                const x = getX(i);
                const y = getY(timeline[i].baseline_balance);
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.stroke();
            ctx.restore();
        }

        // 4. Area fill under projected curve
        const areaGrad = ctx.createLinearGradient(0, plot.y, 0, plot.y + plot.height);
        areaGrad.addColorStop(0, 'rgba(56, 189, 248, 0.16)');
        areaGrad.addColorStop(0.8, 'rgba(56, 189, 248, 0.02)');
        areaGrad.addColorStop(1, 'rgba(56, 189, 248, 0.0)');

        ctx.beginPath();
        for (let i = 0; i < timeline.length; i++) {
            const x = getX(i);
            const y = getY(timeline[i].projected_balance);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.lineTo(getX(timeline.length - 1), plot.y + plot.height);
        ctx.lineTo(getX(0), plot.y + plot.height);
        ctx.closePath();
        ctx.fillStyle = areaGrad;
        ctx.fill();

        // 5. Projected Liquidity Main Stroke Line
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 2.0;
        ctx.beginPath();
        for (let i = 0; i < timeline.length; i++) {
            const x = getX(i);
            const y = getY(timeline[i].projected_balance);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.stroke();

        // 6. X-Axis Dates
        ctx.fillStyle = '#64748b';
        ctx.font = '9.5px "JetBrains Mono", monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';

        const step = Math.max(1, Math.floor(timeline.length / 6));
        for (let i = 0; i < timeline.length; i += step) {
            const x = getX(i);
            const parts = timeline[i].date.split('-');
            const label = `${parts[1]}/${parts[2]}`;
            ctx.fillText(label, x, plot.y + plot.height + 6);
            ctx.fillText(`+${timeline[i].day_index}d`, x, plot.y + plot.height + 18);
        }

        // 7. Interactive Hover Cursor & Marker
        if (this.isHovering && this.hoverIndex >= 0 && this.hoverIndex < timeline.length) {
            const pt = timeline[this.hoverIndex];
            const hX = getX(this.hoverIndex);
            const hY = getY(pt.projected_balance);

            // Vertical crosshair
            ctx.save();
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.25)';
            ctx.setLineDash([2, 2]);
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(hX, plot.y);
            ctx.lineTo(hX, plot.y + plot.height);
            ctx.stroke();
            ctx.restore();

            // Point dot
            ctx.beginPath();
            ctx.arc(hX, hY, 4, 0, Math.PI * 2);
            ctx.fillStyle = pt.is_breach ? '#f43f5e' : '#38bdf8';
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 1.5;
            ctx.fill();
            ctx.stroke();
        }
    }

    _showTooltip(clientX, clientY, pt) {
        let tooltip = document.getElementById('chart-interactive-tooltip');
        if (!tooltip) {
            tooltip = document.createElement('div');
            tooltip.id = 'chart-interactive-tooltip';
            tooltip.className = 'chart-tooltip-floating';
            document.body.appendChild(tooltip);
        }

        const headroom = pt.projected_balance - pt.min_keep;
        const isSafe = headroom >= 0;

        tooltip.innerHTML = `
            <div class="tooltip-header">
                <span class="tooltip-date">Day ${pt.day_index} (${pt.date})</span>
                <span class="tooltip-status ${isSafe ? 'status-safe' : 'status-danger'}">
                    ${isSafe ? 'SAFE' : 'RESERVE BREACH'}
                </span>
            </div>
            <div class="tooltip-row">
                <span class="text-muted">Simulated Balance:</span>
                <span class="font-mono">${this.currency} ${this._formatNumber(pt.projected_balance)}</span>
            </div>
            ${pt.baseline_balance !== undefined ? `
            <div class="tooltip-row text-muted">
                <span>Baseline (No Spend):</span>
                <span class="font-mono">${this.currency} ${this._formatNumber(pt.baseline_balance)}</span>
            </div>
            ` : ''}
            <div class="tooltip-row">
                <span class="text-muted">Reserve Buffer:</span>
                <span class="font-mono" style="color: ${isSafe ? '#10b981' : '#f43f5e'}">
                    ${isSafe ? '+' : ''}${this.currency} ${this._formatNumber(headroom)}
                </span>
            </div>
        `;

        tooltip.style.display = 'block';

        const tRect = tooltip.getBoundingClientRect();
        let top = clientY - tRect.height - 12;
        let left = clientX - tRect.width / 2;

        if (top < 10) top = clientY + 16;
        if (left < 10) left = 10;
        if (left + tRect.width > window.innerWidth - 10) {
            left = window.innerWidth - tRect.width - 10;
        }

        tooltip.style.top = `${top}px`;
        tooltip.style.left = `${left}px`;
    }

    _hideTooltip() {
        const tooltip = document.getElementById('chart-interactive-tooltip');
        if (tooltip) tooltip.style.display = 'none';
    }

    _renderEmptyState() {
        this.ctx.fillStyle = '#64748b';
        this.ctx.font = '12px "Plus Jakarta Sans", sans-serif';
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText('Select a transaction to inspect the liquidity projection', this.width / 2, this.height / 2);
    }

    _formatCompact(num) {
        const abs = Math.abs(num);
        if (abs >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
        if (abs >= 1000) return `${(num / 1000).toFixed(0)}k`;
        return num.toFixed(0);
    }

    _formatNumber(num) {
        return Number(num).toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }
}
