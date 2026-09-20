/** 是否走 wx.login：必须是小程序平台。只看 wx 会误伤 H5 上的不可用桩。 */
export const shouldUseWxLogin = (platform: unknown, wxLogin: unknown) =>
  platform === 'mp-weixin' && typeof wxLogin === 'function'
