function tabScroller() {
    return {
        canScrollLeft: false,
        canScrollRight: false,

        init() {
            this.$nextTick(() => {
                this._updateScrollState();
                const list = this.$refs.tabList;
                if (!list) return;
                list.addEventListener('scroll', () => this._updateScrollState(), { passive: true });
                new ResizeObserver(() => this._updateScrollState()).observe(list);
            });
        },

        _updateScrollState() {
            const list = this.$refs.tabList;
            if (!list) return;
            this.canScrollLeft = list.scrollLeft > 1;
            this.canScrollRight = list.scrollLeft < list.scrollWidth - list.clientWidth - 1;
        },

        scrollTabsLeft() {
            this.$refs.tabList?.scrollBy({ left: -200, behavior: 'smooth' });
        },

        scrollTabsRight() {
            this.$refs.tabList?.scrollBy({ left: 200, behavior: 'smooth' });
        }
    };
}
