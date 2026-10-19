<!-- version 16 -->
<script lang="ts">
  export let icon = 'generic';
  export let label = '';
</script>

<svg
  class="rack-icon"
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width="1.8"
  stroke-linecap="round"
  stroke-linejoin="round"
  role={label ? 'img' : undefined}
  aria-hidden={label ? undefined : 'true'}
>
  {#if label}
    <title>{label}</title>
  {/if}

  {#if icon === 'server'}
    <rect x="4" y="4" width="16" height="16" rx="2"></rect>
    <path d="M7 9h.01M7 15h.01M10 9h7M10 15h7"></path>
  {:else if icon === 'network'}
    <path d="M4 8h13"></path>
    <path d="m14 5 3 3-3 3"></path>
    <path d="M20 16H7"></path>
    <path d="m10 13-3 3 3 3"></path>
  {:else if icon === 'switch'}
    <rect x="3" y="6" width="18" height="12" rx="2"></rect>
    <path d="M7 10h.01M10 10h.01M13 10h.01M16 10h.01M7 14h10"></path>
  {:else if icon === 'storage'}
    <rect x="4" y="4" width="16" height="16" rx="2"></rect>
    <path d="M4 10h16M8 14h.01M8 17h.01M12 14h5"></path>
  {:else if icon === 'power'}
    <path d="M13 2 5 13h6l-1 9 8-12h-6l1-8Z"></path>
  {:else if icon === 'patch-panel'}
    <rect x="3" y="7" width="18" height="10" rx="2"></rect>
    <path d="M6 10h.01M9 10h.01M12 10h.01M15 10h.01M18 10h.01M6 14h.01M9 14h.01M12 14h.01M15 14h.01M18 14h.01"></path>
  {:else if icon === 'shelf'}
    <path d="M3 7h18M5 7v10M19 7v10M3 17h18"></path>
    <path d="M7 12h10"></path>
  {:else if icon === 'camera'}
    <path d="M5 9h3l1.2-2h5.6L16 9h3a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2Z"></path>
    <circle cx="12" cy="14" r="3"></circle>
  {:else if icon === 'accessory'}
    <circle cx="12" cy="12" r="7"></circle>
    <path d="M12 8v4l3 2"></path>
  {:else if icon === 'raspberry-pi'}
    <path d="M12 5c.9-1.8 2.5-2.6 4.2-2.6-.2 1.8-1.1 3.3-2.9 4.2"></path>
    <path d="M11 5C9.6 3.5 8.2 2.8 6.3 3c.4 1.7 1.5 3.1 3.4 3.8"></path>
    <circle cx="8" cy="9" r="2.1"></circle>
    <circle cx="12" cy="8" r="2.2"></circle>
    <circle cx="16" cy="9" r="2.1"></circle>
    <circle cx="7.5" cy="13" r="2.2"></circle>
    <circle cx="12" cy="13.7" r="2.5"></circle>
    <circle cx="16.5" cy="13" r="2.2"></circle>
    <path d="M9 17.5c.9 2.2 2 3.5 3 4 1-.5 2.1-1.8 3-4"></path>
  {:else if icon === 'dell'}
    <circle cx="12" cy="12" r="8.4"></circle>
    <path d="M8 7.8v8.4h3.3a4.2 4.2 0 1 0 0-8.4H8Z"></path>
    <path d="M11.1 7.8 15.8 16.2"></path>
  {:else if icon === 'proxmox'}
    <path d="m12 2 4.2 4.2L12 10.4 7.8 6.2 12 2Z"></path>
    <path d="m18.2 8.2 4 4-4 4-4-4 4-4Z"></path>
    <path d="m5.8 8.2 4 4-4 4-4-4 4-4Z"></path>
    <path d="m12 13.6 4.2 4.2L12 22l-4.2-4.2 4.2-4.2Z"></path>
  {:else if icon === 'router'}
    <rect x="3" y="8" width="18" height="9" rx="2"></rect>
    <path d="M7 8V5M17 8V5M7 5h2M15 5h2M7 12h.01M10 12h.01M13 12h.01M17 12h.01"></path>
  {:else if icon === 'firewall'}
    <path d="M5 5h14v14H5z"></path>
    <path d="M5 10h14M10 5v5M10 10v9M15 10v9"></path>
  {:else if icon === 'wireless-ap'}
    <path d="M4 9a12 12 0 0 1 16 0"></path>
    <path d="M7 12a8 8 0 0 1 10 0"></path>
    <path d="M10 15a4 4 0 0 1 4 0"></path>
    <circle cx="12" cy="18" r="1"></circle>
  {:else if icon === 'ups'}
    <rect x="5" y="3" width="14" height="18" rx="2"></rect>
    <path d="M9 8h6M9 13h.01M12 13h.01M15 13h.01M9 17h6"></path>
  {:else if icon === 'pdu'}
    <rect x="3" y="8" width="18" height="8" rx="2"></rect>
    <circle cx="7" cy="12" r="1.2"></circle>
    <circle cx="12" cy="12" r="1.2"></circle>
    <circle cx="17" cy="12" r="1.2"></circle>
  {:else if icon === 'nas'}
    <rect x="5" y="3" width="14" height="18" rx="2"></rect>
    <path d="M5 9h14M5 15h14M8 6h.01M8 12h.01M8 18h.01"></path>
  {:else if icon === 'desktop'}
    <rect x="4" y="4" width="16" height="11" rx="2"></rect>
    <path d="M9 20h6M12 15v5"></path>
  {:else if icon === 'laptop'}
    <rect x="5" y="4" width="14" height="11" rx="1.5"></rect>
    <path d="M3 18h18M9 18h6"></path>
  {:else if icon === 'kvm'}
    <rect x="4" y="4" width="16" height="12" rx="2"></rect>
    <path d="M8 20h8M12 16v4M8 9h.01M11 9h.01M14 9h.01M17 9h.01M8 12h8"></path>
  {:else if icon === 'modem'}
    <rect x="4" y="10" width="16" height="7" rx="2"></rect>
    <path d="M8 10V6M16 10V6M8 6h2M14 6h2M8 13h.01M12 13h.01M16 13h.01"></path>
  {:else if icon === 'cable'}
    <path d="M7 4v5a5 5 0 0 0 10 0V7"></path>
    <path d="M5 3h4v3H5zM15 4h4v3h-4z"></path>
    <path d="M12 14v6M9 20h6"></path>
  {:else if icon === 'fan'}
    <circle cx="12" cy="12" r="2"></circle>
    <path d="M11 10C7 9 6 6 8 4c3-1 5 2 4 6M14 11c1-4 4-5 6-3 1 3-2 5-6 4M13 14c4 1 5 4 3 6-3 1-5-2-4-6M10 13c-1 4-4 5-6 3-1-3 2-5 6-4"></path>
  {:else if icon === 'rack'}
    <rect x="5" y="2" width="14" height="20" rx="2"></rect>
    <path d="M5 8h14M5 14h14M8 5h.01M8 11h.01M8 17h.01"></path>
  {:else if icon === 'blank-panel'}
    <rect x="3" y="8" width="18" height="8" rx="1"></rect>
    <path d="M6 12h.01M18 12h.01"></path>
  {:else if icon === 'virtual-machine'}
    <rect x="4" y="4" width="11" height="11" rx="2"></rect>
    <rect x="9" y="9" width="11" height="11" rx="2"></rect>
  {:else if icon === 'smart-home'}
    <path d="m4 11 8-7 8 7v9H4v-9Z"></path>
    <path d="M9 20v-5h6v5M8 10h.01M16 10h.01"></path>
  {:else if icon === 'printer'}
    <path d="M7 8V4h10v4"></path>
    <rect x="4" y="8" width="16" height="9" rx="2"></rect>
    <path d="M7 14h10v6H7zM17 11h.01"></path>
  {:else if icon === 'media-player'}
    <rect x="3" y="6" width="18" height="12" rx="2"></rect>
    <path d="m10 10 5 2-5 2v-4Z"></path>
  {:else}
    <path d="m12 3 8 9-8 9-8-9 8-9Z"></path>
    <path d="m12 8 3.5 4L12 16l-3.5-4L12 8Z"></path>
  {/if}
</svg>
