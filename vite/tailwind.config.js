const colors = require('tailwindcss/colors');

module.exports = {
    content: [
        /**
         * HTML. Paths to template files that will contain Tailwind CSS classes.
         */
        '../**/templates/**/*.html',
        '../**/templates/*.html',
        '../**/*.j2',

        /**
         * Python: If you use Tailwind CSS classes in Python, uncomment the following line
         * and make sure the pattern below matches your project structure.
         */
        '../src/**/*.py',
        './node_modules/flowbite/**/*.js',
    ],

    // make sure to safelist these classes when using purge
    safelist: [
        'w-64',
        'w-1/2',
        'rounded-l-lg',
        'rounded-r-lg',
        'bg-gray-200',
        'grid-cols-4',
        'grid-cols-7',
        'h-6',
        'leading-6',
        'h-9',
        'leading-9',
        'shadow-lg',
    ],

    // darkMode: "media", // or 'media' or 'class'
    darkMode: 'class',

    theme: {
        extend: {
            colors: {
                rose: colors.rose,
                // a17t colors
                neutral: colors.slate,
                positive: colors.green,
                urge: colors.violet,
                warning: colors.yellow,
                info: colors.blue,
                critical: colors.red,
                // flowbite colors
                primary: colors.blue,
            },
            minHeight: {
                24: '6rem',
            },
        },
        fontSize: {
            xs: '0.8rem',
            sm: '0.9rem',
            base: '1rem',
            xl: '1.25rem',
            '2xl': '1.563rem',
            '3xl': '1.953rem',
            '4xl': '2.441rem',
            '5xl': '3.052rem',
        },
        fontFamily: {
            primary:
                'var(--family-primary, "Inter", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji")',
            secondary:
                'var(--family-secondary, "Inter", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji")',
            sans: [
                'Inter',
                'system-ui',
                '-apple-system',
                'BlinkMacSystemFont',
                '"Segoe UI"',
                'Roboto',
                '"Helvetica Neue"',
                'Arial',
                '"Noto Sans"',
                'sans-serif',
                '"Apple Color Emoji"',
                '"Segoe UI Emoji"',
                '"Segoe UI Symbol"',
                '"Noto Color Emoji"',
            ],
            serif: [
                'Georgia',
                'Cambria',
                '"Times New Roman"',
                'Times',
                'serif',
            ],
            mono: [
                'Menlo',
                'Monaco',
                'Consolas',
                '"Liberation Mono"',
                '"Courier New"',
                'monospace',
            ],
        },
    },

    variants: {
        extend: {},
    },

    plugins: [
        require('@tailwindcss/typography'),
        require('daisyui'),
        require('a17t'),
        require('flowbite/plugin'),
        // Incompatible w/ Daisyui:
        require('@tailwindcss/forms'),
    ],

    daisyui: {
        prefix: 'dui-',
        themes: [
            {
                abilian: {
                    /* your theme name */ primary:
                        colors.sky[400] /* Primary color */,
                    'primary-focus':
                        colors.sky[600] /* Primary color - focused */,
                    'primary-content':
                        '#ffffff' /* Foreground content color to use on primary color */,

                    secondary: colors.amber[400] /* Secondary color */,
                    'secondary-focus':
                        colors.amber[600] /* Secondary color - focused */,
                    'secondary-content':
                        '#ffffff' /* Foreground content color to use on secondary color */,

                    accent: colors.teal[500] /* Accent color */,
                    'accent-focus':
                        colors.teal[700] /* Accent color - focused */,
                    'accent-content':
                        '#ffffff' /* Foreground content color to use on accent color */,

                    neutral: colors.zinc[500] /* Neutral color */,
                    'neutral-focus':
                        colors.zinc[700] /* Neutral color - focused */,
                    'neutral-content':
                        '#ffffff' /* Foreground content color to use on neutral color */,

                    'base-100':
                        '#ffffff' /* Base color of page, used for blank backgrounds */,
                    'base-200': '#f9fafb' /* Base color, a little darker */,
                    'base-300': '#d1d5db' /* Base color, even more darker */,
                    'base-content':
                        '#1f2937' /* Foreground content color to use on base color */,

                    // 'info': '#2094f3',              /* Info */
                    // 'success': '#009485',           /* Success */
                    // 'warning': '#ff9900',           /* Warning */
                    // 'error': '#ff5724',             /* Error */

                    info: colors.blue[600],
                    success: colors.green[600],
                    warning: colors.orange[600],
                    error: colors.red[600],
                },
            },
        ],
    },
};
