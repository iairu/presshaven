import { Topbar, Badge, HamburgerMenu, DropdownMenu } from '@bsf/force-ui';
import { __ } from '@wordpress/i18n';
import { Link, useLocation } from 'react-router-dom';
import { ChevronDownIcon } from '@heroicons/react/24/outline';
import React from 'react';

import WcarLogo from '@Images/wcar-icon.svg';
import WhatsNew from '@Components/whats-new';
import KnowledgeBase from '@Components/common/KnowledgeBase';
import VersionBadge from '@Components/common/VersionBadge';
import { useStateValue } from '@Store';
import { cn } from '@Utils/helper';
import { FOCUS_RING_CLASS } from '@Components/common/focusStyles';

const Header = () => {
	const [ state ] = useStateValue();
	const urlParams = new URLSearchParams( useLocation().search );
	const currentPath = urlParams.get( 'path' ) || 'dashboard';
	const isLicenseActivated = state?.licenseStatus === '1' ? true : false;

	const menus = [
		{
			name: __( 'Dashboard', 'woo-cart-abandonment-recovery' ),
			path: 'dashboard',
		},
		{
			name: __( 'Follow Up Templates', 'woo-cart-abandonment-recovery' ),
			path: 'follow-up-templates',
		},
		{
			name: __( 'Reports', 'woo-cart-abandonment-recovery' ),
			path: 'reports',
		},
		{
			name: __( 'Activity Log', 'woo-cart-abandonment-recovery' ),
			path: 'activity-log-group',
		},
		{
			name: __( 'Integrations', 'woo-cart-abandonment-recovery' ),
			path: 'integrations',
		},
		{
			name: __( 'Settings', 'woo-cart-abandonment-recovery' ),
			path: 'settings',
		},
	];

	const groups = {
		reports: {
			paths: [ 'follow-up', 'product', 'detailed-report' ],
			children: [
				{
					label: __( 'Follow Up', 'woo-cart-abandonment-recovery' ),
					path: 'follow-up',
				},
				{
					label: __( 'Product', 'woo-cart-abandonment-recovery' ),
					path: 'product',
				},
			],
		},
		'activity-log-group': {
			paths: [ 'activity-log', 'scheduled-jobs' ],
			children: [
				{
					label: __( 'Activity Log', 'woo-cart-abandonment-recovery' ),
					path: 'activity-log',
				},
				{
					label: __( 'Scheduled Jobs', 'woo-cart-abandonment-recovery' ),
					path: 'scheduled-jobs',
				},
			],
		},
	};

	// The menu panel stays mounted while closed and Force UI only turns off its pointer events, so
	// its links would otherwise stay in the tab order. Hide them once the panel is closed, after the
	// close animation.
	const CLOSED_MENU_HIDDEN =
		"[transition-property:color,visibility] [transition-duration:200ms,500ms] [nav[style*='pointer-events:_none']_&]:invisible";
	// Group headings are not Force UI options, so they do not fade with the rest of the list.
	const CLOSED_HEADING_HIDDEN =
		"transition-[opacity,visibility] duration-300 delay-200 [nav[style*='pointer-events:_none']_&]:opacity-0 [nav[style*='pointer-events:_none']_&]:invisible";

	const currentTone = ( path ) =>
		cn(
			'font-medium text-text-secondary hover:text-text-primary',
			currentPath === path && 'font-semibold text-text-primary'
		);

	return (
		<div className="z-30 relative">
			<Topbar className="py-0 h-16 min-h-[unset] border-0 border-b border-solid border-border-subtle">
				<Topbar.Left>
					<Topbar.Item>
						<img
							src={ WcarLogo }
							alt="WooCommerce Cart Abandonment Logo"
							aria-label="WooCommerce Cart Abandonment Logo"
							className="h-8 w-8"
						/>
					</Topbar.Item>
				</Topbar.Left>
				<Topbar.Middle align="left" className="h-full hidden lg:block">
					<Topbar.Item className="h-full">
						<nav
							aria-label={ __( 'Main', 'woo-cart-abandonment-recovery' ) }
							className="flex items-center h-full gap-2"
						>
							{ menus.map( ( menu ) => {
								const group = groups[ menu.path ];
								if ( ! group ) {
									return (
										<Link
											key={ menu.path }
											to={
												cart_abandonment_admin.admin_url +
												`&path=${ menu.path }`
											}
											aria-current={
												currentPath === menu.path
													? 'page'
													: undefined
											}
											className={ cn(
												'px-3 py-2 text-sm whitespace-nowrap inline-flex items-center border-0 border-b-2 border-solid font-medium box-border no-underline h-full transition-colors duration-200',
												currentPath === menu.path
													? 'text-gray-900 border-flamingo-400'
													: 'text-gray-600 hover:text-gray-900 border-transparent'
											) }
										>
											{ menu.name }
										</Link>
									);
								}
								const isActive = group.paths.includes( currentPath );
								return (
									<DropdownMenu
										key={ menu.path }
										className="h-full"
										offset={ 4 }
									>
										<DropdownMenu.Trigger
											className={ cn(
												'px-3 py-2 text-sm whitespace-nowrap inline-flex gap-1 items-center border-0 border-b-2 border-solid cursor-pointer font-medium box-border h-full transition-colors duration-200',
												FOCUS_RING_CLASS,
												isActive
													? 'text-gray-900 border-flamingo-400'
													: 'text-gray-600 hover:text-gray-900 border-transparent'
											) }
										>
											{ menu.name }
											<ChevronDownIcon
												className={ cn(
													'h-4 w-4',
													isActive
														? 'text-gray-900'
														: 'text-gray-600'
												) }
											/>
										</DropdownMenu.Trigger>
										<DropdownMenu.ContentWrapper className="z-999999">
											<DropdownMenu.Content>
												<DropdownMenu.List>
													{ group.children.map( ( child ) => (
														<DropdownMenu.Item
															key={ child.path }
															tabIndex={ -1 }
															className="p-0 [&>*:not(svg)]:m-0"
														>
															<Link
																to={
																	cart_abandonment_admin.admin_url +
																	`&path=${ child.path }`
																}
																aria-current={
																	currentPath ===
																	child.path
																		? 'page'
																		: undefined
																}
																className={ cn(
																	'p-2 w-full text-sm inline-flex items-center rounded-sm box-border no-underline transition-colors duration-200',
																	currentTone( child.path )
																) }
															>
																{ child.label }
															</Link>
														</DropdownMenu.Item>
													) ) }
												</DropdownMenu.List>
											</DropdownMenu.Content>
										</DropdownMenu.ContentWrapper>
									</DropdownMenu>
								);
							} ) }
						</nav>
					</Topbar.Item>
				</Topbar.Middle>
				<Topbar.Right>
					{ cart_abandonment_admin?.is_pro_active && (
						<Topbar.Item className="hidden sm:flex lg:hidden xl:flex">
							{ isLicenseActivated ? (
								<Badge
									label={ __(
										'Valid License',
										'woo-cart-abandonment-recovery'
									) }
									size="xs"
									type="rounded"
									variant="green"
									disableHover
								/>
							) : (
								// Unlicensed, the badge names what to do next, so it links there.
								<Link
									to={
										cart_abandonment_admin.admin_url +
										'&path=settings&tab=license-settings'
									}
									aria-label={ __(
										'Activate your license',
										'woo-cart-abandonment-recovery'
									) }
									className="inline-flex no-underline rounded-sm"
								>
									<Badge
										label={ __(
											'Activate License',
											'woo-cart-abandonment-recovery'
										) }
										size="xs"
										type="rounded"
										variant="red"
									/>
								</Link>
							) }
						</Topbar.Item>
					) }
					{ /* Reference information a merchant needs about once, so it steps aside when the menu needs the room. */ }
					<Topbar.Item className="hidden md:flex lg:hidden xl:flex items-center gap-2">
						<VersionBadge />
					</Topbar.Item>
					{ cart_abandonment_admin?.knowledge_base && (
						<Topbar.Item>
							<KnowledgeBase />
						</Topbar.Item>
					) }
					{ cart_abandonment_admin?.whats_new_rss_feed && (
						<Topbar.Item>
							<WhatsNew />
						</Topbar.Item>
					) }
					<Topbar.Item className="lg:hidden">
						<HamburgerMenu>
							<HamburgerMenu.Toggle className="size-6" />
							<HamburgerMenu.Options className="box-border">
								{ menus.map( ( menu ) => {
									const group = groups[ menu.path ];
									if ( ! group ) {
										return (
											<HamburgerMenu.Option
												key={ menu.path }
												tag="div"
											>
												<Link
													to={
														cart_abandonment_admin.admin_url +
														`&path=${ menu.path }`
													}
													aria-current={
														currentPath ===
														menu.path
															? 'page'
															: undefined
													}
													className={ cn(
														'w-full box-border no-underline',
														currentTone( menu.path ),
														CLOSED_MENU_HIDDEN
													) }
												>
													{ menu.name }
												</Link>
											</HamburgerMenu.Option>
										);
									}
									return (
										<React.Fragment key={ menu.path }>
											<li
												className={ cn(
													'm-0 mt-2 w-full list-none px-2.5 pb-0.5 text-xs font-medium text-text-secondary',
													CLOSED_HEADING_HIDDEN
												) }
											>
												{ menu.name }
											</li>
											{ group.children.map( ( child ) => (
												<HamburgerMenu.Option
													key={ child.path }
													tag="div"
												>
													<Link
														to={
															cart_abandonment_admin.admin_url +
															`&path=${ child.path }`
														}
														aria-current={
															currentPath ===
															child.path
																? 'page'
																: undefined
														}
														className={ cn(
															'w-full pl-3 box-border no-underline',
															currentTone( child.path ),
															CLOSED_MENU_HIDDEN
														) }
													>
														{ child.label }
													</Link>
												</HamburgerMenu.Option>
											) ) }
										</React.Fragment>
									);
								} ) }
							</HamburgerMenu.Options>
						</HamburgerMenu>
					</Topbar.Item>
				</Topbar.Right>
			</Topbar>
		</div>
	);
};

export default Header;
