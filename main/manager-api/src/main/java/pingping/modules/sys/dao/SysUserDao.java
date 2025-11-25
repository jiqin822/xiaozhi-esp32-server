package pingping.modules.sys.dao;

import org.apache.ibatis.annotations.Mapper;

import pingping.common.dao.BaseDao;
import pingping.modules.sys.entity.SysUserEntity;

/**
 * 系统用户
 */
@Mapper
public interface SysUserDao extends BaseDao<SysUserEntity> {

}