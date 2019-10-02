import torch,logging
import numpy as np
logger = logging.getLogger(__name__)


class_ids = []
def get_loss(config):
   global class_ids
   class_ids = config['data_handling']['class_nums']

   if 'loss' not in config:
      raise Exception('must include "loss" section in config file')

   loss_config = config['loss']

   if 'func' not in loss_config:
      raise Exception('must include "func" loss section in config file')

   if loss_config['func'] in locals():
      return locals(loss_config['func'])
   elif 'CrossEntropyLoss' in loss_config['func']:
      weight = None
      if 'weight' in loss_config:
         weight = loss_config['loss_weight']
      size_average = None
      if 'size_average' in loss_config:
         size_average = loss_config['loss_size_average']
      ignore_index = -100
      if 'ignore_index' in loss_config:
         ignore_index = loss_config['loss_ignore_index']
      reduce = None
      if 'reduce' in loss_config:
         reduce = loss_config['loss_reduce']
      reduction = 'mean'
      if 'reduction' in loss_config:
         reduction = loss_config['loss_reduction']

      return torch.nn.CrossEntropyLoss(weight,size_average,ignore_index,reduce,reduction)
   
   else:
      raise Exception('%s loss function is not recognized' % loss_config['func'])


def get_accuracy(config):
   if 'CrossEntropyLoss' in config['loss']['func'] or 'pointnet_class_loss' in config['loss']['func']:
      
      return multiclass_acc
   if config['loss']['func'] in ['pixel_wise_cross_entry','pixelwise_crossentropy_weighted']:
      return pixel_wise_accuracy
   else:
      if 'func' not in config['model']:
         raise Exception('loss function not defined in config')
      else:
         raise Exception('%s loss function is not recognized' % config['loss']['func'])


def pointnet_class_loss(pred,targets,end_points,reg_weight=0.001,device='cpu'):
   criterion = torch.nn.CrossEntropyLoss()  # use a Classification Cross-Entropy loss
   classify_loss = criterion(pred, targets)
   # print('prediction = %s' % torch.nn.Softmax()(pred) )
   
   # Enforce the transformation as orthogonal matrix
   mat_loss = 0
   # if 'input_trans' in end_points:
   #    tran = end_points['input_trans']

   #    diff = torch.mean(torch.bmm(tran, tran.permute(0, 2, 1)), 0)
   #    mat_loss += torch.nn.MSELoss()(diff, torch.eye(tran.shape[1]))

   if 'feature_trans' in end_points:
      tran = end_points['feature_trans']

      diff = torch.mean(torch.bmm(tran, tran.permute(0, 2, 1)), 0)
      mat_loss += torch.nn.MSELoss()(diff, torch.eye(tran.shape[1],device=device))

   # print('criterion = %s mat_loss = %s' % (classify_loss.item(),mat_loss.item()))
   loss = classify_loss + mat_loss * reg_weight

   return loss


def multiclass_acc(pred,targets):

   # logger.info('>> pred = %s targets = %s',pred,targets)
   pred = torch.softmax(pred,dim=1)
   # logger.info('gt = %s',pred)
   pred = pred.argmax(dim=1).float()
   # logger.info('argmax = %s',pred)

   eq = torch.eq(pred,targets.float())
   # logger.info('eq = %s',eq)

   return torch.sum(eq).float() / float(targets.shape[0])


def pixel_wise_accuracy(pred,targets,device='cpu'):
   # need to calculate the accuracy over all points

   pred_stat = torch.nn.Softmax(dim=1)(pred)
   _,pred_value = pred_stat.max(dim=1)

   correct = (targets.long() == pred_value).sum()
   total = float(pred_value.numel())

   acc = correct.float() / total

   return acc


def pixel_wise_cross_entry(pred,targets,endpoints,device='cpu',reg_weight=0.001):

   # pred.shape = [N_batch, N_class, N_points]
   # targets.shape = [N_batch,N_points]

   classify_loss = torch.nn.CrossEntropyLoss()(pred,targets.long())
   # logger.info('classify_loss = %s',classify_loss)

   # Enforce the transformation as orthogonal matrix
   # feature_trans = endpoints['feature_trans']  # BxKxK
   # logger.info('feature_trans[0] = %s %s',torch.max(feature_trans[0]),torch.min(feature_trans[0]))
   # K = feature_trans.shape[1]
   # mat_diff = feature_trans.matmul(feature_trans.transpose(2,1))

   # logger.info('mat_diff[0] = %s %s',torch.max(mat_diff[0]),torch.min(mat_diff[0]))
   # mat_diff -= torch.tensor(np.eye(K), dtype=torch.float32)

   # mat_diff_loss = torch.sum(mat_diff ** 2) / 2.
   # logger.info('mat_diff_loss = %s',mat_diff_loss)

   # combined_loss = classify_loss + mat_diff_loss * reg_weight

   return classify_loss


def pixelwise_crossentropy_focal(pred,targets,endpoints,weights,device='cpu',gamma=2.,alpha=1.):

   # pred.shape = [N_batch, N_class, N_points]
   # targets.shape = [N_batch,N_points]

   nclasses = pred.shape[1]
   npoints = targets.shape[1]
   nbatch = targets.shape[0]

   model_out = torch.nn.LogSoftmax(dim=1)(pred)
   ce = model_out * targets

   focal_weight = targets * torch.pow(1 - model_out,gamma)

   focal_loss = focal_weight * alpha * ce * mask

   proportional_weights = []
   for i in range(len(class_ids)):
      proportional_weights.append((targets == i).sum())
   proportional_weights = torch.Tensor(proportional_weights)
   proportional_weights = proportional_weights.sum() / proportional_weights
   proportional_weights[proportional_weights == float('Inf')] = 0

   # logger.info('weights = %s',weights)

   loss_value = torch.nn.CrossEntropyLoss(weight=proportional_weights,reduction='none')(pred,targets.long())
   # logger.info('loss_value = %s',loss_value)
   # logger.info('weights = %s',weights)

   loss_value = loss_value * weights
   # logger.info('loss_value = %s',loss_value)
   loss_value = torch.mean(loss_value)

   return loss_value


def pixelwise_crossentropy_weighted(pred,targets,endpoints,weights=None,device='cpu'):
   # for semantic segmentation, need to compare class
   # prediction for each point AND need to weight by the
   # number of pixels for each point

   # flatten targets and predictions

   # pred.shape = [N_batch, N_class, N_points]
   # targets.shape = [N_batch,N_points]
   # logger.info(f'pred = {pred.shape}  targets = {targets.shape}')

   nclasses = pred.shape[1]
   npoints = targets.shape[1]
   nbatch = targets.shape[0]

   proportional_weights = []
   for i in range(len(class_ids)):
      proportional_weights.append((targets == i).sum())
   proportional_weights = torch.Tensor(proportional_weights)
   proportional_weights = proportional_weights.sum() / proportional_weights
   proportional_weights[proportional_weights == float('Inf')] = 0

   # logger.info('weights = %s',weights)

   loss_value = torch.nn.CrossEntropyLoss(weight=proportional_weights,reduction='none')(pred,targets.long())
   # logger.info('loss_value = %s',loss_value)
   # logger.info('weights = %s',weights)

   loss_value = loss_value * weights
   # logger.info('loss_value = %s',loss_value)
   loss_value = torch.mean(loss_value)

   return loss_value

